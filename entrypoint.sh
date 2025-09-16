#!/bin/bash

# Entrypoint script for Interview Chatbot Assistant Docker container
set -e

# Start Xvfb (X Virtual Framebuffer) for headless browser operations
echo "🖥️ Starting Xvfb for headless browser operations..."
Xvfb :99 -screen 0 1920x1080x24 -ac +extension GLX +render -noreset &
export DISPLAY=:99

# Wait for Xvfb to start
sleep 2

# Set proper permissions for directories
echo "📁 Setting up directories and permissions..."
mkdir -p /app/results /app/logs /app/screenshots /app/recordings
chmod 755 /app/results /app/logs /app/screenshots /app/recordings

# Verify Playwright installation
echo "🎭 Verifying Playwright browser installation..."
python -c "from playwright.sync_api import sync_playwright; print('✅ Playwright ready')" || {
    echo "❌ Playwright verification failed"
    exit 1
}

# Verify OpenCV installation
echo "👁️ Verifying OpenCV installation..."
python -c "import cv2; print(f'✅ OpenCV {cv2.__version__} ready')" || {
    echo "❌ OpenCV verification failed"
    exit 1
}

# Verify audio dependencies
echo "🔊 Verifying audio processing dependencies..."
python -c "import librosa; print('✅ Audio processing ready')" || {
    echo "❌ Audio processing verification failed"
    exit 1
}

# Verify ML dependencies
echo "🤖 Verifying ML dependencies..."
python -c "import torch, ultralytics; print('✅ ML dependencies ready')" || {
    echo "❌ ML dependencies verification failed"
    exit 1
}

# Set environment variables for optimal performance
export PYTHONUNBUFFERED=1
export PYTHONDONTWRITEBYTECODE=1
export OPENCV_LOG_LEVEL=ERROR
export PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Health check endpoint (optional)
if [ "$1" = "health" ]; then
    echo "🏥 Health check passed"
    exit 0
fi

echo "🚀 Starting Interview Chatbot Assistant..."
echo "📝 Command: $@"

# Execute the main command
exec "$@"
