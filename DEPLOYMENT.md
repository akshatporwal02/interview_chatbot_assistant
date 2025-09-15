# Deployment Guide for Interview Chatbot Assistant

## Overview
This document provides instructions for deploying the Interview Chatbot Assistant on Northflank developer sandbox.

## Prerequisites
- Docker installed locally (for testing)
- Northflank account with developer sandbox access
- Required API keys (Daily.co, OpenAI, Email credentials)

## Environment Variables
Copy `.env.template` to `.env` and configure the following variables:

```bash
# Required
DAILY_API_KEY=your_daily_api_key_here
EMAIL_USERNAME=your_email@gmail.com
EMAIL_PASSWORD=your_app_password_here
EMAIL_DEFAULT_RECEIVER=recipient@example.com

# Optional
OPENAI_API_KEY=your_openai_api_key_here
DEBUG=false
LOG_LEVEL=INFO
```

## Local Testing
1. Build and run locally:
```bash
docker-compose up --build
```

2. Test the application:
```bash
docker exec -it interview-chatbot-assistant python code/launcher.py
```

## Northflank Deployment

### Step 1: Prepare Repository
1. Ensure all files are committed to your Git repository
2. Push to GitHub/GitLab

### Step 2: Create Northflank Service
1. Login to Northflank dashboard
2. Create new service from Git repository
3. Select your repository and branch
4. Choose "Dockerfile" as build method

### Step 3: Configure Environment
1. Add environment variables in Northflank dashboard:
   - `DAILY_API_KEY`
   - `EMAIL_USERNAME`
   - `EMAIL_PASSWORD`
   - `EMAIL_DEFAULT_RECEIVER`
   - `OPENAI_API_KEY` (optional)

### Step 4: Configure Resources
- **CPU**: 1 vCPU minimum (2 vCPU recommended)
- **Memory**: 2GB minimum (4GB recommended)
- **Storage**: 10GB for session data and reports

### Step 5: Deploy
1. Click "Deploy" in Northflank dashboard
2. Monitor build logs for any issues
3. Wait for deployment to complete

## Application Structure
```
interview_chatbot_assistant/
├── code/
│   ├── launcher.py          # Main entry point
│   ├── main.py             # Core application logic
│   ├── automation/         # Browser automation
│   ├── detection/          # AI detection modules
│   ├── services/           # Email and messaging
│   └── utils/              # Utility functions
├── config/
│   └── config.yaml         # Application configuration
├── Dockerfile              # Container definition
├── requirements.txt        # Python dependencies
└── .dockerignore          # Docker ignore rules
```

## Key Features
- **Face Detection**: Monitors candidate presence
- **Eye Tracking**: Detects suspicious eye movements
- **Object Detection**: Identifies forbidden objects
- **Audio Transcription**: Converts speech to text
- **Report Generation**: Creates PDF reports
- **Email Notifications**: Sends reports automatically

## Troubleshooting

### Common Issues
1. **Build Failures**: Check requirements.txt for version conflicts
2. **Permission Errors**: Ensure proper file permissions in Dockerfile
3. **Memory Issues**: Increase allocated memory in Northflank
4. **Browser Issues**: Verify Playwright installation

### Logs
Monitor application logs in Northflank dashboard:
- Build logs for deployment issues
- Runtime logs for application errors

### Health Checks
The application includes health checks that verify:
- Python runtime availability
- Core dependencies loaded

## Security Considerations
- Never commit `.env` files to repository
- Use Northflank's secret management for sensitive data
- Regularly update dependencies for security patches
- Monitor resource usage to prevent abuse

## Performance Optimization
- Use multi-stage Docker builds for smaller images
- Implement proper caching strategies
- Monitor CPU and memory usage
- Scale horizontally if needed

## Support
For deployment issues:
1. Check Northflank documentation
2. Review application logs
3. Verify environment configuration
4. Test locally with Docker first
