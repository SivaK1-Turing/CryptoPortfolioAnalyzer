# Multi-stage Dockerfile for Crypto Portfolio Analyzer
# Optimized for production deployment with security and size considerations

# Build stage for linting and type checking
FROM python:3.8-slim as lint-stage

WORKDIR /app

# Install system dependencies for linting
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install linting dependencies
COPY pyproject.toml requirements.txt ./
RUN pip install --no-cache-dir flake8 mypy bandit black isort

# Copy source code
COPY crypto_portfolio_analyzer/ ./crypto_portfolio_analyzer/
COPY .flake8 ./

# Run linting checks
RUN flake8 crypto_portfolio_analyzer --count --statistics
RUN mypy crypto_portfolio_analyzer --ignore-missing-imports

# Test stage for running tests
FROM python:3.8-slim as test-stage

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install test dependencies
COPY pyproject.toml requirements.txt ./
RUN pip install --no-cache-dir -e .[test]

# Copy source code and tests
COPY crypto_portfolio_analyzer/ ./crypto_portfolio_analyzer/
COPY tests/ ./tests/

# Run tests with coverage
RUN pytest --cov=crypto_portfolio_analyzer --cov-report=term-missing --cov-fail-under=80

# Production build stage
FROM python:3.8-slim as build-stage

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY pyproject.toml requirements.txt ./
RUN pip install --no-cache-dir --user -e .

# Final production stage
FROM python:3.8-slim as production

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set working directory
WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from build stage
COPY --from=build-stage /root/.local /home/appuser/.local

# Copy application code
COPY crypto_portfolio_analyzer/ ./crypto_portfolio_analyzer/
COPY pyproject.toml requirements.txt ./

# Create necessary directories
RUN mkdir -p /app/logs /app/data /app/cache \
    && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Add local Python packages to PATH
ENV PATH=/home/appuser/.local/bin:$PATH

# Set Python path
ENV PYTHONPATH=/app

# Configure application
ENV CRYPTO_PORTFOLIO_LOGGING_LEVEL=INFO
ENV CRYPTO_PORTFOLIO_CACHE_BACKEND=memory
ENV CRYPTO_PORTFOLIO_DATABASE_URL=sqlite:///data/crypto_portfolio.db

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import crypto_portfolio_analyzer; print('OK')" || exit 1

# Expose port (if running as web service in future)
EXPOSE 8000

# Default command
ENTRYPOINT ["python", "-m", "crypto_portfolio_analyzer.cli"]
CMD ["--help"]

# Labels for metadata
LABEL org.opencontainers.image.title="Crypto Portfolio Analyzer"
LABEL org.opencontainers.image.description="A sophisticated CLI tool for cryptocurrency portfolio management"
LABEL org.opencontainers.image.version="0.1.0"
LABEL org.opencontainers.image.authors="Crypto Portfolio Analyzer Team"
LABEL org.opencontainers.image.source="https://github.com/crypto-portfolio-analyzer/crypto-portfolio-analyzer"
LABEL org.opencontainers.image.licenses="MIT"
