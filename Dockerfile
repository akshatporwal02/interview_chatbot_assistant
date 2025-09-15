# Use Python 3.11 slim image as base for better performance
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    DISPLAY=:99

# Install system dependencies required for the application
RUN apt-get update && apt-get install -y \
    # System utilities
    wget \
    curl \
    gnupg \
    software-properties-common \
    apt-transport-https \
    ca-certificates \
    # Audio dependencies
    libasound2-dev \
    portaudio19-dev \
    # OpenCV dependencies
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libglib2.0-0 \
    libgtk-3-0 \
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    libv4l-dev \
    libxvidcore-dev \
    libx264-dev \
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    libatlas-base-dev \
    # Browser dependencies for Playwright
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxss1 \
    libgconf-2-4 \
    libxrandr2 \
    libasound2 \
    libpangocairo-1.0-0 \
    libatk1.0-0 \
    libcairo-gobject2 \
    libgtk-3-0 \
    libgdk-pixbuf2.0-0 \
    # PDF generation dependencies
    wkhtmltopdf \
    xvfb \
    # Font dependencies
    fonts-liberation \
    fonts-dejavu-core \
    fontconfig \
    # Process management
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Create application directory
WORKDIR /app

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium && \
    playwright install-deps chromium

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
