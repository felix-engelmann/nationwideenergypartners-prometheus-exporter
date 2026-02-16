# Use UV base image with Python & uv preinstalled
FROM ghcr.io/astral-sh/uv:alpine

# Set working directory
WORKDIR /app

# Copy project dependency files
COPY pyproject.toml uv.lock* ./

# Install dependencies using uv
RUN uv sync --locked

# Copy exporter code and .env file
COPY exporter.py ./

# Expose the metrics port
EXPOSE 8000

# Start the exporter
CMD ["uv", "run", "python", "exporter.py"]
