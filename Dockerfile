# Use Python 3.11 full image (not slim) to avoid apt-get issues
FROM python:3.11

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DISPLAY=:99

# Minimal system dependencies required by OpenCV headless at runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Create application directory
WORKDIR /app

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies with specific torch CPU versions
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch==2.0.1+cpu torchvision==0.15.2+cpu --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt --ignore-installed

# Create necessary directories
RUN mkdir -p /app/session_data/logs \
             /app/session_data/recordings \
             /app/session_data/transcripts_doc \
             /app/reports/generated/images \
             /app/reports/generated

# Copy application code
COPY . .

# Set proper permissions
RUN chmod +x code/launcher.py && \
    chmod +x code/main.py

# Copy and set permissions for entrypoint script (before switching user)
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Create a non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# Expose port (if your application serves HTTP)
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# Set the working directory to code folder
WORKDIR /app/code

# Use entrypoint script for better initialization
ENTRYPOINT ["/app/entrypoint.sh"]

# Default command - run the launcher
CMD ["python", "launcher.py"]
