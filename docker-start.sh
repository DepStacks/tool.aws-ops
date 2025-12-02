#!/bin/bash
# Start AWS Ops MCP Server locally with Docker

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting AWS Ops MCP Server...${NC}"

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}Warning: .env file not found. Creating from .env.example...${NC}"
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "Please update .env with your configuration"
    else
        echo "Creating minimal .env file..."
        cat > .env << EOF
AWS_REGION=us-east-1
MCP_AUTH_TOKEN=dev-token
EOF
    fi
fi

# Build and start the container
docker-compose up --build -d

# Wait for the service to be healthy
echo "Waiting for service to be ready..."
sleep 3

# Check if service is running
if docker-compose ps | grep -q "Up"; then
    echo -e "${GREEN}✓ AWS Ops MCP Server is running!${NC}"
    echo ""
    echo "Server URL: http://localhost:8100/sse"
    echo "Health check: http://localhost:8100/healthz"
    echo ""
    echo "To view logs: docker-compose logs -f"
    echo "To stop: docker-compose down"
else
    echo "Failed to start service. Check logs with: docker-compose logs"
    exit 1
fi
