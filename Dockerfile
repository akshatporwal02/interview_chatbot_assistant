# Use Python 3.10 slim as base for better compatibility
FROM python:3.10-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV DEBIAN_FRONTEND=noninteractive
ENV DISPLAY=:99

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # Essential build tools
    build-essential \
    pkg-config \
    # Audio processing dependencies
    ffmpeg \
    libsndfile1-dev \
    # Computer vision dependencies
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgstreamer1.0-0 \
    libgstreamer-plugins-base1.0-0 \
    # PDF generation dependencies
    wkhtmltopdf \
    # Font dependencies
    fonts-liberation \
    fonts-dejavu-core \
    fontconfig \
    # Display dependencies for headless browser
    xvfb \
    # Browser dependencies
    wget \
    gnupg \
    ca-certificates \
    # Process management
    supervisor \
    # Cleanup
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js for Playwright
RUN wget -qO- https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y nodejs

# Create app directory and user
RUN useradd -m -u 1001 appuser
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies with CPU-only PyTorch
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch==2.0.1+cpu torchvision==0.15.2+cpu --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# Install Playwright and browsers
RUN pip install playwright==1.39.0 && \
    playwright install chromium && \
    playwright install-deps chromium

# Copy application code
COPY . .

# Create necessary directories with proper permissions
RUN mkdir -p /app/results /app/logs /app/screenshots /app/recordings && \
    chmod 755 /app/results /app/logs /app/screenshots /app/recordings

# Pre-create X11 socket directory for Xvfb
RUN mkdir -p /tmp/.X11-unix && \
    chmod 1777 /tmp/.X11-unix

# Copy and set up entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Set ownership to app user
RUN chown -R appuser:appuser /app && \
    chown appuser:appuser /entrypoint.sh

# Switch to non-root user
USER appuser

# Expose port for health checks
EXPOSE 8080

# Set entrypoint
ENTRYPOINT ["/entrypoint.sh"]

# Default command
CMD ["python", "code/launcher.py"]
