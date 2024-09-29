#!/bin/sh

echo "Getting configuration..."

# Set default values for environment variables
DEBUG=${DEBUG:-false}
MQTT_HOST=${MQTT_HOST:-localhost}
SMTP_LISTEN_PORT=${SMTP_LISTEN_PORT:-25}
SMTP_AUTH_REQUIRED=${SMTP_AUTH_REQUIRED:-false}
SMTP_RELAY_HOST=${SMTP_RELAY_HOST:-""}
SMTP_RELAY_PORT=${SMTP_RELAY_PORT:-""}
SMTP_RELAY_USER=${SMTP_RELAY_USER:-""}
SMTP_RELAY_PASS=${SMTP_RELAY_PASS:-""}
SMTP_RELAY_STARTTLS=${SMTP_RELAY_STARTTLS:-false}
SMTP_RELAY_TIMEOUT_SECS=${SMTP_RELAY_TIMEOUT_SECS:-60}
MQTT_PORT=${MQTT_PORT:-1883}
MQTT_USER=${MQTT_USER:-""}
MQTT_PASS=${MQTT_PASS:-""}
MQTT_TOPIC=${MQTT_TOPIC:-"smtp2mqtt"}
PUBLISH_ATTACHMENTS=${PUBLISH_ATTACHMENTS:-true}
SAVE_ATTACHMENTS=${SAVE_ATTACHMENTS:-false}

# Debugging output
if [ "$DEBUG" = "true" ]; then
    echo "Debug mode is enabled."
    echo "MQTT_HOST: $MQTT_HOST"
fi

# Set the attachment save directory if needed
if [ "$SAVE_ATTACHMENTS" = "true" ]; then
    SAVE_ATTACHMENTS_DIR=${SAVE_ATTACHMENTS_DIR:-"/share/smtp2mqtt"}
    echo "Creating attachment save directory: $SAVE_ATTACHMENTS_DIR"
    mkdir -p "$SAVE_ATTACHMENTS_DIR" || {
        echo "Failed to create directory: $SAVE_ATTACHMENTS_DIR"
        exit 1
    }
fi

echo "Starting application..."
exec python3 /app/smtp2mqtt.py
