# interview_chatbot_assistant

A modular Python application for monitoring and analyzing interview sessions using computer vision and audio detection. The system detects face presence, eye movement, multiple faces, forbidden objects, and audio events, generating comprehensive reports for each session.

## Features

- **Face Detection:** Detects presence and disappearance of faces.
- **Eye Tracking:** Monitors gaze direction and eye movement.
- **Multiple Face Detection:** Flags presence of more than one face.
- **Object Detection:** Detects forbidden objects in the frame.
- **Audio Detection:** Monitors and flags audio events.
- **Screenshot Capture:** Captures screenshots during the session.
- **Report Generation:** Generates PDF reports with violation summaries.
- **Configurable Thresholds:** All detection thresholds and severity levels are configurable via YAML.
