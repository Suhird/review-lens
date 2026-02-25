#!/usr/bin/env bash
set -e

echo "========================================"
echo "  ReviewLens - Initialization Script"
echo "========================================"

# Check for required tools
if ! command -v docker &> /dev/null; then
  echo "ERROR: Docker is not installed. Please install Docker Desktop first."
  exit 1
fi

if ! command -v docker compose &> /dev/null && ! docker compose version &> /dev/null; then
  echo "ERROR: Docker Compose is not available. Please install Docker Desktop."
  exit 1
fi

# Check for .env file
if [ ! -f .env ]; then
  echo "ERROR: .env file not found. Please copy .env.example to .env and fill in your credentials."
  echo "  cp .env.example .env"
  exit 1
fi

echo ""
echo "[1/4] Verifying native Ollama is running..."
OLLAMA_READY=false
for i in $(seq 1 5); do
  if curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; then
    OLLAMA_READY=true
    break
  fi
  echo "  Waiting for local Ollama... attempt $i/5"
  sleep 2
done

if [ "$OLLAMA_READY" = false ]; then
  echo "ERROR: Local Ollama is not responding on http://localhost:11434."
  echo "Please install Ollama from ollama.com and ensure it is running."
  exit 1
fi

# Get model from .env, default to mistral
OLLAMA_MODEL=$(grep '^OLLAMA_MODEL=' .env | cut -d '=' -f2)
MODEL=${OLLAMA_MODEL:-mistral}

echo ""
echo "[2/4] Ensuring $MODEL model is downloaded natively..."
ollama pull "$MODEL" || echo "Warning: Could not pull $MODEL automatically. Run 'ollama pull $MODEL' if needed."

echo ""
echo "[3/4] Starting all remaining services..."
docker compose up -d postgres redis backend frontend

echo ""
echo "[4/4] Waiting for all services to be healthy..."
MAX_WAIT=120
WAITED=0
while [ $WAITED -lt $MAX_WAIT ]; do
  BACKEND_STATUS=$(docker inspect --format='{{.State.Health.Status}}' reviewlens_backend 2>/dev/null || echo "starting")
  if [ "$BACKEND_STATUS" = "healthy" ]; then
    break
  fi
  sleep 5
  WAITED=$((WAITED + 5))
  echo "  Backend status: $BACKEND_STATUS ($WAITED/$MAX_WAIT seconds)"
done

echo ""
echo "========================================"
echo "  ReviewLens is ready!"
echo "========================================"
echo ""
echo "  Frontend:  http://localhost:3000"
echo "  API:       http://localhost:8000"
echo "  API Docs:  http://localhost:8000/docs"
echo ""
echo "To stop all services: docker compose down"
echo "To view logs:         docker compose logs -f"
echo ""
