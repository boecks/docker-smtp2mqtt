ARG BUILD_FROM=python:3.11-alpine
FROM ${BUILD_FROM}

WORKDIR /app

COPY ./smtp2mqtt/start.sh ./smtp2mqtt/smtp2mqtt.py /app/

RUN chmod 755 /app/start.sh

RUN apk add --no-cache python3 py3-pip && pip3 install paho-mqtt aiosmtpd

ENTRYPOINT ["/app/start.sh"]
