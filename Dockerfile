# Multi-stage build for optimized Northflank deployment
FROM mcr.microsoft.com/playwright/python:v1.39.0-jammy as base

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV DEBIAN_FRONTEND=noninteractive
ENV DISPLAY=:99

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # Audio processing dependencies
    portaudio19-dev \
    libasound2-dev \
    libsndfile1-dev \
    ffmpeg \
    # Computer vision dependencies
    libopencv-dev \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    # PDF generation dependencies
    wkhtmltopdf \
    # Font dependencies for headless operation
    fonts-liberation \
    fonts-dejavu-core \
    fontconfig \
    # Display dependencies for headless browser
    xvfb \
    x11vnc \
    fluxbox \
    # Process management
    supervisor \
    # Cleanup
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium && \
    playwright install-deps chromium

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/results /app/logs /app/screenshots /app/recordings

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app && \
    chown appuser:appuser /entrypoint.sh

# Switch to non-root user
USER appuser

# Expose port (if needed for health checks)
EXPOSE 8080

# Set entrypoint
ENTRYPOINT ["/entrypoint.sh"]

# Default command
CMD ["python", "code/launcher.py"]
