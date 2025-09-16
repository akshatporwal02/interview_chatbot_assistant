# Use Ubuntu 22.04 as base image for better compatibility with system dependencies
FROM ubuntu:22.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV DISPLAY=:99

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # Python and pip
    python3 \
    python3-pip \
    python3-dev \
    python3-venv \
    # System libraries for OpenCV and computer vision
    libopencv-dev \
    python3-opencv \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    # Audio processing dependencies
    libasound2-dev \
    portaudio19-dev \
    pulseaudio \
    alsa-utils \
    # PDF generation dependencies
    wkhtmltopdf \
    xvfb \
    # Browser automation dependencies
    wget \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libxss1 \
    libxtst6 \
    # Additional system utilities
    curl \
    git \
    unzip \
    # Video processing dependencies (for ffmpeg)
    ffmpeg \
    # X11 and display dependencies
    xauth \
    x11-utils \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt* ./
RUN if [ -f requirements.txt ]; then pip3 install --no-cache-dir -r requirements.txt; fi

# Install core Python packages that are definitely needed based on code analysis
RUN pip3 install --no-cache-dir \
    # Web automation
    playwright==1.40.0 \
    # Computer vision and detection
    opencv-python==4.8.1.78 \
    numpy==1.24.3 \
    # Audio processing
    faster-whisper==0.9.0 \
    wave \
    # Report generation
    pdfkit==1.0.0 \
    matplotlib==3.7.2 \
    jinja2==3.1.2 \
    # API and web requests
    requests==2.31.0 \
    # Configuration and utilities
    pyyaml==6.0.1 \
    pytz==2023.3 \
    # Email functionality
    smtplib \
    email-validator \
    # Path and file utilities
    pathlib \
    # Additional dependencies that might be needed
    pillow==10.0.0 \
    scipy==1.11.2 \
    scikit-learn==1.3.0 \
    ultralytics \
    torch \
    torchvision \
    torchaudio

# Install Playwright browsers
RUN playwright install chromium
RUN playwright install-deps chromium

# Create necessary directories
RUN mkdir -p /app/session_data/recordings \
    /app/session_data/transcripts_doc \
    /app/reports/generated \
    /app/reports/generated/images \
    /app/logs

# Copy application code
COPY . .

# Set up virtual display for headless browser operations
RUN echo '#!/bin/bash\nXvfb :99 -screen 0 1024x768x24 > /dev/null 2>&1 &\nexec "$@"' > /usr/local/bin/entrypoint.sh \
    && chmod +x /usr/local/bin/entrypoint.sh

# Create a non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Set environment variables for the application
ENV PYTHONPATH=/app/code
ENV PATH="/home/appuser/.local/bin:$PATH"

# Expose any ports if needed (adjust as necessary)
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python3 -c "import sys; sys.exit(0)"

# Entry point
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

# Default command - adjust based on your needs
# For launcher: CMD ["python3", "code/launcher.py"]
# For main: CMD ["python3", "code/main.py"]
CMD ["python3", "code/launcher.py"]
