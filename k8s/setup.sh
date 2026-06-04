#!/bin/bash
# HR AI Agents — One-shot Kubernetes cluster setup
# Requires: Docker Desktop with Kubernetes enabled, helm, kubectl
# Run once: bash k8s/setup.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NAMESPACE="hr-ai"

log() { echo "[$(date +%H:%M:%S)] $*"; }
ok()  { echo "  ✅ $*"; }
err() { echo "  ❌ $*"; exit 1; }

# ──────────────────────────────────────────────────────────
# 0. Pre-flight checks
# ──────────────────────────────────────────────────────────
log "Pre-flight checks..."
kubectl config current-context | grep -q "docker-desktop" \
  || err "Switch context: kubectl config use-context docker-desktop"
kubectl get nodes | grep -q "Ready" || err "Cluster not ready"
command -v helm >/dev/null || err "helm not found — brew install helm"
ok "Cluster ready"

# ──────────────────────────────────────────────────────────
# 1. /etc/hosts
# ──────────────────────────────────────────────────────────
log "Configuring /etc/hosts..."
if ! grep -q "hr-ai.local" /etc/hosts; then
  echo "127.0.0.1 hr-ai.local argocd.hr-ai.local grafana.hr-ai.local langfuse.hr-ai.local app.hr-ai.local" \
    | sudo tee -a /etc/hosts > /dev/null
  ok "/etc/hosts updated"
else
  ok "/etc/hosts already configured"
fi

# ──────────────────────────────────────────────────────────
# 2. Namespace + RBAC + PVCs
# ──────────────────────────────────────────────────────────
log "Applying namespace, RBAC, PVCs..."
kubectl apply -f "$REPO_ROOT/k8s/namespace.yaml"
ok "Namespace $NAMESPACE ready"

# ──────────────────────────────────────────────────────────
# 3. NGINX Ingress Controller
# ──────────────────────────────────────────────────────────
log "Installing NGINX Ingress Controller..."
if ! kubectl get ns ingress-nginx &>/dev/null; then
  kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.10.1/deploy/static/provider/cloud/deploy.yaml
  kubectl wait --namespace ingress-nginx \
    --for=condition=ready pod \
    --selector=app.kubernetes.io/component=controller \
    --timeout=120s
  ok "NGINX Ingress ready"
else
  ok "NGINX Ingress already installed"
fi

# ──────────────────────────────────────────────────────────
# 4. Metrics Server (for HPA CPU metrics)
# ──────────────────────────────────────────────────────────
log "Installing Metrics Server..."
if ! kubectl get deployment metrics-server -n kube-system &>/dev/null; then
  kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
  kubectl patch deployment metrics-server -n kube-system \
    --type=json \
    -p='[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
  ok "Metrics Server installed"
else
  ok "Metrics Server already installed"
fi

# ──────────────────────────────────────────────────────────
# 5. KEDA
# ──────────────────────────────────────────────────────────
log "Installing KEDA..."
helm repo add kedacore https://kedacore.github.io/charts --force-update
if ! kubectl get ns keda &>/dev/null; then
  helm install keda kedacore/keda --namespace keda --create-namespace
  ok "KEDA installed"
else
  ok "KEDA already installed"
fi

# ──────────────────────────────────────────────────────────
# 6. ArgoCD
# ──────────────────────────────────────────────────────────
log "Installing ArgoCD..."
if ! kubectl get ns argocd &>/dev/null; then
  kubectl create namespace argocd
  kubectl apply -n argocd \
    -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
  kubectl wait --namespace argocd \
    --for=condition=available deployment/argocd-server \
    --timeout=180s
  ok "ArgoCD installed"
else
  ok "ArgoCD already installed"
fi

# ──────────────────────────────────────────────────────────
# 7. ArgoCD Project + Applications
# ──────────────────────────────────────────────────────────
log "Applying ArgoCD project and applications..."
kubectl apply -f "$REPO_ROOT/argocd/projects/hr-ai-project.yaml"
for app in "$REPO_ROOT/argocd/applications/"*.yaml; do
  kubectl apply -f "$app"
done
ok "ArgoCD apps registered"

# ──────────────────────────────────────────────────────────
# 8. Infrastructure (PostgreSQL, Redis, Ingress)
# ──────────────────────────────────────────────────────────
log "Deploying infrastructure..."
kubectl apply -f "$REPO_ROOT/k8s/infra/"
ok "Infrastructure deployed"

# ──────────────────────────────────────────────────────────
# 9. MLX-LM
# ──────────────────────────────────────────────────────────
log "Deploying MLX-LM server..."
kubectl apply -f "$REPO_ROOT/k8s/mlx-lm/"
ok "MLX-LM manifests applied (model download may take ~5 min)"

# ──────────────────────────────────────────────────────────
# 10. Agents
# ──────────────────────────────────────────────────────────
log "Deploying agents..."
kubectl apply -f "$REPO_ROOT/k8s/agents/"
ok "Agents deployed"

# ──────────────────────────────────────────────────────────
# 11. Observability (optional — takes ~3 min)
# ──────────────────────────────────────────────────────────
log "Installing Prometheus + Grafana..."
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts --force-update
helm repo add grafana https://grafana.github.io/helm-charts --force-update
helm repo update
kubectl create namespace observability --dry-run=client -o yaml | kubectl apply -f -

helm upgrade --install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  --namespace observability \
  -f "$REPO_ROOT/k8s/monitoring/prometheus-config.yaml" \
  --wait --timeout 180s 2>/dev/null && ok "Prometheus + Grafana installed" \
  || echo "  ⚠️  Prometheus install skipped (non-fatal)"

helm upgrade --install loki grafana/loki-stack \
  --namespace observability \
  -f "$REPO_ROOT/observability/loki/promtail-config.yaml" \
  --wait --timeout 120s 2>/dev/null && ok "Loki + Promtail installed" \
  || echo "  ⚠️  Loki install skipped (non-fatal)"

# ──────────────────────────────────────────────────────────
# Done
# ──────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════"
echo "  ✅  HR AI Agents cluster setup complete!"
echo "══════════════════════════════════════════════"
echo ""
echo "  ArgoCD UI:   kubectl port-forward svc/argocd-server -n argocd 8443:443"
echo "               https://localhost:8443"
echo "  ArgoCD pass: kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d"
echo ""
echo "  Grafana:     http://grafana.hr-ai.local  (admin / hr-ai-grafana-2026)"
echo "  API:         http://hr-ai.local/api/v1/health"
echo ""
echo "  Watch pods:  kubectl get pods -n hr-ai -w"
