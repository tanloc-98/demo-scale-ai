import sys
import os

# Add project root to sys.path so `backend.*` imports work when running from red-teaming/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
