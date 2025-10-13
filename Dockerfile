# Multi-stage build for optimized Northflank deployment
FROM mcr.microsoft.com/playwright/python:v1.39.0-jammy AS base

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV DEBIAN_FRONTEND=noninteractive
ENV DISPLAY=:99
# Model/cache locations to persist within the image (or mount a volume here at runtime)
ENV ULTRALYTICS_CACHE_DIR=/app/models/ultralytics
ENV HF_HOME=/app/models/hf_cache
ENV CT2_CACHE_DIR=/app/models/ct2_cache

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # Audio processing dependencies
    portaudio19-dev \
    libasound2-dev \
    libsndfile1-dev \
    libavcodec-dev \
    libavformat-dev \
    libavutil-dev \
    libswscale-dev \
    libswresample-dev \
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
    # Utilities
    curl \
    # Cleanup
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu \
        torch==2.3.1+cpu torchvision==0.18.1+cpu torchaudio==2.3.1+cpu && \
    pip install --no-cache-dir --prefer-binary -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium && \
    playwright install-deps chromium

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/results /app/logs /app/screenshots /app/recordings \
    && mkdir -p /app/models /app/models/ultralytics /app/models/hf_cache /app/models/ct2_cache

# Pre-download and cache model weights at build time to avoid runtime downloads
# 1) YOLOv8l weights
RUN curl -L -o /app/models/yolov8l.pt \
    https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8l.pt

# 2) Faster-Whisper medium model (CT2 format) will populate CT2_CACHE_DIR
RUN python - <<'PY'
from faster_whisper import WhisperModel
print('Downloading faster-whisper medium model to cache...')
WhisperModel('medium', device='cpu', compute_type='int8')
print('Done.')
PY

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Set correct ownership to built-in Playwright user (pwuser)
RUN chown -R pwuser:pwuser /app && \
    chown pwuser:pwuser /entrypoint.sh

# Pre-create X11 socket directory for Xvfb when running as non-root
RUN mkdir -p /tmp/.X11-unix && \
    chmod 1777 /tmp/.X11-unix && \
    chown root:root /tmp/.X11-unix

USER pwuser

# Expose port (if needed for health checks)
EXPOSE 8080

# Set entrypoint
ENTRYPOINT ["/entrypoint.sh"]

# # Default command
# CMD ["python", "code/main.py"]
