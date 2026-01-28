FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    bash \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.cargo/bin:${PATH}"

# Create working directories
WORKDIR /workspace
RUN mkdir -p /test-repos /test-tools

# Copy entrypoint and test scripts (these are part of the image)
COPY entrypoint.sh /entrypoint.sh
COPY test-e2e.sh /test-e2e.sh
RUN chmod +x /entrypoint.sh /test-e2e.sh

# Set entrypoint
ENTRYPOINT ["/entrypoint.sh"]
