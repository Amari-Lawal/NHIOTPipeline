# Use lightweight python base image
FROM python:3.11-slim

# Install system dependencies (git is required for OTA git-push trigger, curl for health check)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory inside the container
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project files
COPY . .

# Expose the port FastAPI runs on
EXPOSE 8080

# Set environment variable to run python unbuffered (for real-time logging)
ENV PYTHONUNBUFFERED=1
ENV RUNNING_IN_DOCKER=true

# Command to run the dashboard FastAPI application
CMD ["python", "Dashboard/app.py"]
