FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (needed for audio/video processing sometimes)
# libgl1-mesa-glx and libglib2.0-0 are common for cv2 if needed, 
# but for basic livekit audio agent usually just python is fine.
# We'll stick to minimal unless needed.

# Copy requirements if they exist, or install minimal
COPY requirements.txt .

# Install dependencies
# Note: Ensure livekit-plugins-openai is in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Environment variables should be injected at runtime, but we can set defaults
ENV PYTHONUNBUFFERED=1

# Run the agent
CMD ["python", "agent.py", "start"]
