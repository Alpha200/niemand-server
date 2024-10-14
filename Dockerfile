FROM python:3.12-slim-bullseye

RUN apt-get update && \
    apt-get install -y libssl-dev libasound2 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

EXPOSE 8001

# Install hatch and hatchling
RUN pip install hatchling hatch

# Copy the pyproject.toml and other necessary files
COPY pyproject.toml ./

# Create the virtual environment and install dependencies
RUN hatch env create

ENV OPENHAB_AUTH_TOKEN=""
ENV OPENHAB_DEFAULT_ROOM=""
ENV OPENHAB_SERVER_URL=""
ENV TRAINCHECK_STATION_FROM=""
ENV TRAINCHECK_STATION_VIA=""
ENV UVICORN_PORT=8001
ENV WEATHER_DEFAULT_PLACE=""
ENV TANDOOR_SERVER_URL=""
ENV TANDOOR_ACCESS_TOKEN=""
ENV OPENAI_TOKEN=""
ENV RASA_BASE_URI="http://nlu-http:5005"
ENV VOSK_BASE_URI="ws://vosk-server-websocket:2700"
ENV MIMIC_TTS_URI="http://mimic-http:59125/api/tts"

COPY src src/

WORKDIR /app/src

CMD ["hatch", "run", "uvicorn", "--host", "0.0.0.0", "niemand_server.main:app"]