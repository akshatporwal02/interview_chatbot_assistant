# Docker Deployment Guide for Interview Chatbot Assistant

This guide provides comprehensive instructions for deploying the Interview Chatbot Assistant using Docker, specifically optimized for Northflank deployment.

## 🏗️ Architecture Overview

The application consists of:
- **Launcher**: Polls Daily.co rooms and spawns bot instances
- **Main Bot**: Joins meetings, captures screenshots, processes ML models
- **ML Processing**: Face detection, eye tracking, object detection
- **Report Generation**: OpenAI LLM analysis and PDF report creation
- **Browser Automation**: Playwright-based Daily.co room interaction

## 📋 Prerequisites

- Docker and Docker Compose installed
- Daily.co API key
- OpenAI API key
- Email credentials (for report delivery)

## 🚀 Quick Start

### 1. Environment Setup

Copy the environment template and fill in your credentials:

```bash
cp .env.template .env
```

Edit `.env` with your actual API keys and configuration.

### 2. Local Development

Build and run locally using Docker Compose:

```bash
# Build the image
docker-compose build

# Run the application
docker-compose up -d

# View logs
docker-compose logs -f interview-chatbot
```

### 3. Northflank Deployment

#### Option A: Direct Docker Build

1. Push your code to a Git repository
2. In Northflank, create a new service
3. Select "Build from Git repository"
4. Configure build settings:
   - **Build Method**: Dockerfile
   - **Dockerfile Path**: `./Dockerfile`
   - **Build Context**: `.`

#### Option B: Container Registry

```bash
# Build and tag the image
docker build -t your-registry/interview-chatbot:latest .

# Push to your container registry
docker push your-registry/interview-chatbot:latest
```

Then deploy from the container registry in Northflank.

## ⚙️ Configuration

### Environment Variables

Set these environment variables in Northflank:

| Variable | Description | Required |
|----------|-------------|----------|
| `DAILY_API_KEY` | Daily.co API key | Yes |
| `OPENAI_API_KEY` | OpenAI API key | Yes |
| `EMAIL_SENDER` | Sender email address | Yes |
| `EMAIL_PASSWORD` | Email password/app password | Yes |
| `EMAIL_RECEIVER` | Default report recipient | No |
| `DEBUG` | Enable debug logging | No |
| `HEADLESS_MODE` | Run browser in headless mode | No |

### Resource Requirements

Recommended Northflank resource allocation:

- **CPU**: 1-2 vCPUs
- **Memory**: 2-4 GB RAM
- **Storage**: 10-20 GB (for recordings and reports)

## 🔧 Docker Image Features

### Base Image
- Uses official Playwright Python image for browser automation
- Pre-installed Chromium browser with dependencies

### System Dependencies
- **Audio Processing**: PortAudio, ALSA, FFmpeg
- **Computer Vision**: OpenCV, CUDA support
- **PDF Generation**: wkhtmltopdf
- **Display**: Xvfb for headless operation
- **Fonts**: Liberation and DejaVu fonts

### Security Features
- Non-root user execution
- Minimal attack surface
- Secure file permissions

## 📁 Volume Mounts

For persistent data, mount these directories:

```yaml
volumes:
  - ./results:/app/results      # Generated reports
  - ./logs:/app/logs           # Application logs
  - ./screenshots:/app/screenshots  # Captured images
  - ./recordings:/app/recordings    # Audio recordings
```

## 🏥 Health Checks

The container includes a health check endpoint:

```bash
# Manual health check
docker exec container_name /entrypoint.sh health
```

## 🐛 Troubleshooting

### Common Issues

1. **Browser Launch Failures**
   - Ensure Xvfb is running
   - Check display environment variable
   - Verify Playwright installation

2. **Audio Processing Errors**
   - Check PortAudio installation
   - Verify audio device permissions
   - Ensure FFmpeg is available

3. **OpenCV Issues**
   - Verify OpenGL libraries
   - Check system dependencies
   - Ensure proper permissions

4. **Memory Issues**
   - Increase container memory limits
   - Monitor resource usage
   - Optimize detection intervals

### Debug Commands

```bash
# Check container logs
docker logs container_name

# Interactive shell
docker exec -it container_name /bin/bash

# Verify dependencies
docker exec container_name python -c "import cv2, playwright, torch; print('All deps OK')"
```

## 🔄 Updates and Maintenance

### Updating the Application

1. Update your code repository
2. Rebuild the Docker image
3. Redeploy on Northflank

### Monitoring

- Monitor container logs for errors
- Check resource usage regularly
- Verify report generation success
- Monitor API rate limits

## 📊 Performance Optimization

### For Production

1. **Resource Allocation**
   - Scale CPU based on concurrent rooms
   - Allocate sufficient memory for ML models
   - Use SSD storage for better I/O

2. **Configuration Tuning**
   - Adjust detection intervals
   - Optimize screenshot frequency
   - Configure appropriate timeouts

3. **Scaling**
   - Use horizontal scaling for multiple rooms
   - Implement load balancing if needed
   - Consider database for state management

## 🔐 Security Considerations

- Store API keys securely in Northflank secrets
- Use environment-specific configurations
- Regularly update base images
- Monitor for security vulnerabilities
- Implement proper logging without sensitive data

## 📞 Support

For deployment issues:
1. Check container logs first
2. Verify environment variables
3. Test dependencies individually
4. Review Northflank deployment logs

This deployment setup is optimized for reliability and performance on Northflank's infrastructure.
