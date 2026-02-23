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
echo "[1/5] Starting Ollama service..."
docker compose up -d ollama

echo ""
echo "[2/5] Waiting for Ollama to be ready (30 seconds)..."
sleep 30

# Verify Ollama is up
OLLAMA_READY=false
for i in $(seq 1 10); do
  if docker exec reviewlens_ollama curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; then
    OLLAMA_READY=true
    break
  fi
  echo "  Waiting for Ollama... attempt $i/10"
  sleep 5
done

if [ "$OLLAMA_READY" = false ]; then
  echo "ERROR: Ollama did not start in time. Check logs: docker logs reviewlens_ollama"
  exit 1
fi

echo ""
echo "[3/5] Pulling Mistral model (this may take several minutes on first run)..."
docker exec reviewlens_ollama ollama pull mistral

echo ""
echo "[4/5] Starting all remaining services..."
docker compose up -d postgres redis backend frontend

echo ""
echo "[5/5] Waiting for all services to be healthy..."
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
