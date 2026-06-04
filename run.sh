#!/bin/bash
set -e

echo "🚀 Starting HR AI Agents System..."

# 1. Install backend requirements and start backend server
echo "📦 Setting up Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

echo "📦 Installing backend dependencies..."
pip install -r requirements.txt

echo "🔄 Starting FastAPI Backend on port 8000..."
# We run uvicorn in the background
export PYTHONPATH=$(pwd)
uvicorn backend.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

echo "✅ Backend started! (PID: $BACKEND_PID)"
sleep 2

# 2. Setup and start frontend
echo "📦 Installing frontend dependencies..."
cd frontend
npm install

echo "🔄 Starting Next.js Frontend on port 3000..."
npm run dev &
FRONTEND_PID=$!

echo "✅ Frontend started! (PID: $FRONTEND_PID)"
echo ""
echo "🌟 SYSTEM READY!"
echo "👉 Dashboard UI: http://localhost:3000"
echo "👉 Backend API:  http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop both servers."

# Wait for both processes
wait $BACKEND_PID $FRONTEND_PID
