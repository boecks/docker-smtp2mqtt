# Use a specific Python version as the base image
ARG BUILD_FROM=python:3.11-alpine
FROM ${BUILD_FROM}

# Set the working directory
WORKDIR /app

# Install required packages and Python dependencies
RUN apk add --no-cache python3 py3-pip \
    && pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir paho-mqtt aiosmtpd

# Copy application files
COPY . .

# Ensure the start script is executable
RUN chmod +x start.sh

# Define the command to run the application
CMD ["/app/start.sh"]
