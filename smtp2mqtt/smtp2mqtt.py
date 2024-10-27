#!/usr/bin/env python3
import asyncio
import email
import logging
import os
import signal
import time
import json
import base64
import smtplib
import uuid
from email.policy import default
from aiosmtpd.controller import Controller
from aiosmtpd.smtp import AuthResult
from paho.mqtt import publish

##
## Original source from https://github.com/wicol/emqtt
## Heavily modified by https://github.com/boecks in 2024
##

# Default configurations
config_defaults = {
    "SMTP_BIND_ADDRESS": "0.0.0.0",
    "SMTP_LISTEN_PORT": "25",
    "SMTP_AUTH_REQUIRED": "True",
    "SMTP_RELAY_HOST": None,
    "SMTP_RELAY_PORT": None,
    "SMTP_RELAY_USER": None,
    "SMTP_RELAY_PASS": None,
    "SMTP_RELAY_STARTTLS": "False",
    "SMTP_RELAY_TIMEOUT_SECS": "30",
    "MQTT_HOST": "localhost",
    "MQTT_PORT": "1883",
    "MQTT_USER": None,
    "MQTT_PASS": None,
    "MQTT_TOPIC": "smtp2mqtt",
    "PUBLISH_ATTACHMENTS": "True",
    "SAVE_ATTACHMENTS": "True",
    "SAVE_ATTACHMENTS_DIR": "/share/smtp2mqtt",
    "DEBUG": "True",
}

# Load configuration from environment variables
config = {key: os.getenv(key, default) for key, default in config_defaults.items()}

# Convert config values to appropriate types
for key, value in config.items():
    if value is None:
        config[key] = config_defaults[key]
    elif value.lower() in ["true", "false"]:
        config[key] = value.lower() == "true"
    else:
        config[key] = value

# Logging configuration
log_level = logging.DEBUG if config["DEBUG"] else logging.INFO
log = logging.getLogger("smtp2mqtt")
log.setLevel(log_level)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(uuid)s - %(message)s"))
log.addHandler(ch)

class SMTP2MQTTHandler:
    """Handles SMTP messages and publishes them to MQTT."""
    
    def __init__(self, loop):
        self.loop = loop
        self.quit = False
        self.published_message_uuids = set()
        signal.signal(signal.SIGTERM, self.set_quit)
        signal.signal(signal.SIGINT, self.set_quit)

    async def handle_DATA(self, server, session, envelope):
        """Handles incoming email messages."""
        log_extra = {'uuid': str(uuid.uuid4())[:8]}
        log.info("Received message from %s", envelope.mail_from, extra=log_extra)

        msg = email.message_from_bytes(envelope.original_content, policy=default)
        payload = {
            'uuid': log_extra['uuid'], 
            'headers': {k.lower(): v for k, v in msg.items()}, 
            'mime_parts': []
        }
        topic = f"{config['MQTT_TOPIC']}/{envelope.mail_from.replace('/', '')}"

        # Extract message body and attachments
        self.extract_body(msg, payload)
        self.handle_attachments(msg, payload, log_extra)

        # Publish to MQTT
        log.info("Publishing message to MQTT...", extra=log_extra)
        await self.mqtt_publish(topic, json.dumps(payload), log_extra)

        # Relay the original message if configured
        if config["SMTP_RELAY_HOST"]:
            self.smtp_relay(msg, envelope.mail_from, envelope.rcpt_tos, log_extra)

        return "250 Message accepted for delivery"

    def extract_body(self, msg, payload):
        """Extracts the message body from the email message."""
        try:
            if msg.is_multipart():
                for part in msg.iter_parts():
                    if part.get_content_type() in ['text/plain', 'text/html']:
                        body_part = self.create_body_part(part)
                        payload['mime_parts'].append(body_part)
            else:
                body_part = self.create_body_part(msg)
                payload['mime_parts'].append(body_part)
        except Exception as e:
            log.error("Failed to extract body: %s", e, extra={'uuid': payload['uuid']})

    def create_body_part(self, msg_part):
        """Creates a body part dictionary from a message part."""
        return {
            'best_guess': msg_part.get_content_type(),
            'headers': {k.lower(): v for k, v in msg_part.items()},
            'content': msg_part.get_content()
        }

    def handle_attachments(self, msg, payload, log_extra):
        """Handles the attachments of the email message."""
        try:
            for attachment in msg.iter_attachments():
                mime_part = {
                    'best_guess': 'attachment',
                    'headers': {k.lower(): v for k, v in attachment.items()}
                }
                content = attachment.get_content()

                log.info(f"Attachment detected: {attachment.get_filename()}, Content Type: {attachment.get_content_type()}", extra=log_extra)

                if config["PUBLISH_ATTACHMENTS"]:
                    mime_part['content'] = base64.b64encode(content).decode("utf8", errors="replace")
                else:
                    mime_part['content'] = "<not configured to publish attachment data>"

                self.save_attachment(attachment, log_extra, content, mime_part)

        except Exception as e:
            log.error("Failed to handle attachments: %s", e, extra=log_extra)

    def save_attachment(self, attachment, log_extra, content, mime_part):
        """Saves the attachment to the configured directory."""
        if config["SAVE_ATTACHMENTS_DIR"]:
            filename = f"{log_extra['uuid']}_{os.path.basename(attachment.get_filename())}"
            file_path = os.path.join(config["SAVE_ATTACHMENTS_DIR"], filename)
            log.info(f"Saving attachment to {file_path}", extra=log_extra)
            try:
                with open(file_path, "wb") as f:
                    f.write(content)
                log.info(f"Successfully saved attachment: {file_path}", extra=log_extra)
                mime_part['saved_file_name'] = file_path
            except Exception as e:
                log.error(f"Failed to save attachment to {file_path}: {e}", extra=log_extra)

    async def mqtt_publish(self, topic, payload, log_extra):
        """Publishes the payload to the specified MQTT topic."""
        # Ensure payload is a dictionary
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            log.error("Failed to decode JSON payload", extra=log_extra)
            return

        message_uuid = payload.get("uuid")

        # Check for duplicate messages
        if message_uuid in self.published_message_uuids:
            log.warning(f"Message with UUID {message_uuid} has already been published. Skipping...")
            return

        log.debug(f'Publishing to {topic}', extra=log_extra)
        try:
            publish.single(
                topic,
                json.dumps(payload),
                hostname=config["MQTT_HOST"],
                port=int(config["MQTT_PORT"] or 1883),
                auth={
                    "username": config["MQTT_USER"],
                    "password": config["MQTT_PASS"],
                } if config["MQTT_USER"] else None,
            )
            log.debug(f'Successfully published to {topic}', extra=log_extra)
            self.published_message_uuids.add(message_uuid)
        except Exception as e:
            log.exception("Failed publishing", extra=log_extra)

    def smtp_relay(self, msg, mail_from, rcpt_tos, log_extra):
        """Relays the email to the configured SMTP relay server."""
        log.info("Relaying email", extra=log_extra)
        try:
            with smtplib.SMTP(
                host=config["SMTP_RELAY_HOST"],
                port=int(config["SMTP_RELAY_PORT"] or 25),
                timeout=int(config["SMTP_RELAY_TIMEOUT_SECS"] or 10),
            ) as relay:
                if config["SMTP_RELAY_STARTTLS"]:
                    relay.starttls()
                if config["SMTP_RELAY_USER"]:
                    relay.login(user=config["SMTP_RELAY_USER"], password=config["SMTP_RELAY_PASS"])
                relay.send_message(msg, mail_from, rcpt_tos)
                log.info("Successfully relayed email to %s", rcpt_tos, extra=log_extra)
        except Exception as e:
            log.exception("Failed relaying", extra=log_extra)

    def set_quit(self, *args):
        """Handles termination signals to gracefully shut down the server."""
        log.info("Quitting...", extra={'uuid': 'main thread'})
        self.quit = True

def dummy_auth_function(server, session, envelope, mechanism, auth_data):
    """Dummy authentication function that always succeeds."""
    log.info("Authenticating...", extra={'uuid': 'main thread'})
    return AuthResult(success=True)

if __name__ == "__main__":
    log.debug(", ".join([f"{k}={v}" for k, v in config.items()]), extra={'uuid': 'main thread'})

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    controller = Controller(
        handler=SMTP2MQTTHandler(loop),
        loop=loop,
        hostname=config["SMTP_BIND_ADDRESS"],
        port=int(config["SMTP_LISTEN_PORT"]),
        authenticator=dummy_auth_function,
        auth_required=config["SMTP_AUTH_REQUIRED"],
        auth_require_tls=not config["SMTP_AUTH_REQUIRED"],
    )
    
    controller.start()
    log.info("Running", extra={'uuid': 'main thread'})
    
    try:
        while not controller.handler.quit:
            time.sleep(0.5)
        controller.stop()
    except Exception as e:
        controller.stop()
        log.exception("Error occurred while running the server", extra={'uuid': 'main thread'})
        raise
