#!/bin/bash

# Entrypoint script for Interview Chatbot Assistant
set -e

# Create necessary directories if they don't exist
mkdir -p /app/session_data/logs
mkdir -p /app/session_data/recordings
mkdir -p /app/session_data/transcripts_doc
mkdir -p /app/reports/generated/images

# Set proper permissions
chmod -R 755 /app/session_data
chmod -R 755 /app/reports

# Start Xvfb for headless browser operations
echo "Starting Xvfb for headless browser operations..."
Xvfb :99 -screen 0 1920x1080x24 &
export DISPLAY=:99

# Wait for Xvfb to start
sleep 2

# Verify environment variables
echo "Checking environment variables..."
if [ -z "$DAILY_API_KEY" ]; then
    echo "WARNING: DAILY_API_KEY not set"
fi

if [ -z "$EMAIL_USERNAME" ]; then
    echo "WARNING: EMAIL_USERNAME not set"
fi

# Change to code directory
cd /app/code

# Execute the main application
echo "Starting Interview Chatbot Assistant..."
exec "$@"
