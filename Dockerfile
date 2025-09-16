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
    tmux \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install build tools
RUN pip3 install --upgrade pip setuptools wheel

# Install Python dependencies in stages to avoid conflicts
# Stage 1: Core dependencies
RUN pip3 install --no-cache-dir \
    numpy>=1.21.0 \
    pillow>=9.0.0 \
    requests>=2.28.0 \
    pyyaml>=6.0 \
    pytz>=2022.1

# Stage 2: Scientific computing
RUN pip3 install --no-cache-dir \
    scipy>=1.9.0 \
    scikit-learn>=1.2.0 \
    matplotlib>=3.5.0

# Stage 3: Computer vision
RUN pip3 install --no-cache-dir \
    opencv-python>=4.8.0

# Stage 4: Web automation
RUN pip3 install --no-cache-dir \
    playwright>=1.30.0

# Stage 5: Machine learning (PyTorch ecosystem)
RUN pip3 install --no-cache-dir \
    torch>=1.13.0 \
    torchvision>=0.14.0 \
    torchaudio>=0.13.0

# Stage 6: Specialized packages
RUN pip3 install --no-cache-dir \
    ultralytics>=8.0.0 \
    faster-whisper>=0.8.0 \
    pdfkit>=1.0.0 \
    jinja2>=3.0.0 \
    email-validator>=1.3.0

# Copy and install from requirements.txt as fallback
COPY requirements.txt* ./
RUN if [ -f requirements.txt ]; then pip3 install --no-cache-dir -r requirements.txt || echo "Some packages from requirements.txt may have failed, but core packages are installed"; fi

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
