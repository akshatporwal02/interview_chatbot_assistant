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
# Directories for reports when running with relative paths under /app
mkdir -p /app/reports/generated/images
mkdir -p /app/reports/violation_captures
chmod -R 775 /app/reports
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
echo "🔊 Verifying audio transcription dependency (faster-whisper)..."
python -c "from faster_whisper import WhisperModel; print('✅ faster-whisper ready')" || {
    echo "❌ faster-whisper verification failed"
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

# if [ -n "$ROOM_URL" ]; then
#     set -- "$@" --url "$ROOM_URL"
# fi
# if [ -n "$ROOM_NAME" ]; then
#     set -- "$@" --room "$ROOM_NAME"
# fi

#!/bin/bash

# entrypoint.sh
# Read environment variables passed from the webhook service
MEETING_ID=${MEETING_ID:-""}
ROOM_NAME=${ROOM_NAME:-""}

# Validate that required parameters are present
if [ -z "$MEETING_ID" ] || [ -z "$ROOM_NAME" ]; then
    echo "Error: MEETING_ID and ROOM_NAME environment variables are required"
    exit 1
fi

echo "Starting job with Meeting ID: $MEETING_ID, Room Name: $ROOM_NAME"

# Execute main.py with the parameters
python code/main.py "$MEETING_ID" "$ROOM_NAME"

# Execute the main command
# exec "$@"
