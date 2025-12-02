FROM python:3.11-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY server.py .
COPY config.py .
COPY services/ ./services/

# Expose port for HTTP transport
EXPOSE 8000

# Run the MCP server with HTTP transport
CMD ["python", "-u", "server.py", "--http", "8000"]
