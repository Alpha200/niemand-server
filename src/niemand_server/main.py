import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Optional, Annotated

import aiohttp
import uvicorn
import azure.cognitiveservices.speech as speechsdk
from fastapi import FastAPI, WebSocket, Depends, HTTPException, Header
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel
from .containers import Container
from dependency_injector.wiring import inject, Provide
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from .service.skill_manager import SkillManagerService
from .skill.skill import ProcessResponse, map_context
from .service.aireport import AiReportService


class ProcessPayloadContext(BaseModel):
    room: str | None


class ProcessPayload(BaseModel):
    utterance: str
    context: ProcessPayloadContext | None


class TTSMessage(BaseModel):
    message: str

class ReportResponse(BaseModel):
    report: str

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s - %(name)s - %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)
logging.getLogger("apscheduler").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)
time.tzset()

container = Container()
container.config.calendar.url.from_env("CALENDAR_CALDAV_URL")
container.config.calendar.username.from_env("CALENDAR_USER")
container.config.calendar.password.from_env("CALENDAR_PASSWORD")
container.config.calendar.calendar_names.from_env("CALENDAR_CALENDARS")
container.config.openhab.default_room.from_env('OPENHAB_DEFAULT_ROOM', None)
container.config.openhab.server_url.from_env('OPENHAB_SERVER_URL', 'http://localhost:8080')
container.config.openhab.auth_token.from_env('OPENHAB_AUTH_TOKEN', None)
container.config.openhab.language.from_env('OPENHAB_LANGUAGE', 'de')
container.config.traincheck.station_from.from_env('TRAINCHECK_STATION_FROM', None)
container.config.traincheck.station_via.from_env('TRAINCHECK_STATION_VIA', None)
container.config.weather.default_place.from_env('WEATHER_DEFAULT_PLACE', None)
container.config.openai.openai_api_key.from_env('OPENAI_TOKEN', None)
container.config.location.traccar_url.from_env('TRACCAR_URL', None)
container.config.location.traccar_username.from_env('TRACCAR_USERNAME', None)
container.config.location.traccar_password.from_env('TRACCAR_PASSWORD', None)
container.config.location.traccar_device_id.from_env('TRACCAR_DEVICE_ID', None)
container.config.shopping.kitchenowl_url.from_env('KITCHENOWL_URL', None)
container.config.shopping.kitchenowl_access_token.from_env('KITCHENOWL_TOKEN', None)
container.config.shopping.shoppinglist_id.from_env('SHOPPINGLIST_ID', None)

RASA_BASE_URI = os.environ.get('RASA_BASE_URI', 'http://localhost:5005')
AZURE_SPEECH_ACCESS_TOKEN = os.environ.get('AZURE_SPEECH_ACCESS_TOKEN', None)
AZURE_SPEECH_REGION = os.environ.get('AZURE_SPEECH_REGION', None)
AZURE_SPEECH_LANGUAGE = os.environ.get('AZURE_SPEECH_LANGUAGE', 'de-DE')

api_token = os.environ.get('API_TOKEN', None)

def verify_token(authorization: Annotated[str | None, Header()] = None):
    if authorization != f"Bearer {api_token}":
        raise HTTPException(
            status_code=401,
            detail="Invalid API token",
            headers={"WWW-Authenticate": "Bearer"},
        )
app = FastAPI(dependencies=[Depends(verify_token)])

@app.post("/assistant/process")
@inject
async def process(payload: ProcessPayload, skill_manager: SkillManagerService = Depends(Provide[Container.skill_manager])) -> ProcessResponse:
    async with aiohttp.ClientSession() as session:
        result = await session.post(f'{RASA_BASE_URI}/model/parse', json=dict(text=payload.utterance))
        result_json = await result.json()
        context = map_context(
            result_json,
            payload.utterance,
            payload.context.room if payload.context is not None else None
        )
        skill_result = await skill_manager.run_skills(context)

        if skill_result is not None:
            return ProcessResponse(response=skill_result.response, context=context)
        else:
            return ProcessResponse(response="", context=context)

@app.get("/assistant/report/text")
@inject
async def generate_text_report(aireport: AiReportService = Depends(Provide[Container.aireport_service])) -> ReportResponse:
    report = await aireport.generate_text_report()
    return ReportResponse(report=report)

@app.get("/assistant/report/speach")
@inject
async def generate_voice_report(aireport: AiReportService = Depends(Provide[Container.aireport_service])) -> StreamingResponse:
    return StreamingResponse(aireport.generate_voice_report(), media_type="audio/mpeg")


@app.post("/assistant/azure-tts")
async def azure_tts(message: TTSMessage):
    speech_config = speechsdk.SpeechConfig(
        subscription=AZURE_SPEECH_ACCESS_TOKEN,
        region=AZURE_SPEECH_REGION
    )
    speech_config.speech_synthesis_voice_name = "de-DE-AmalaNeural"
    speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config)

    text = message.message
    ssml_text = f"<speak version='1.0' xml:lang='de-DE'><voice name='de-DE-AmalaNeural'><prosody rate='20%'>{text}</prosody></voice></speak>"

    result = speech_synthesizer.speak_ssml_async(ssml_text).get()
    audio_data = result.audio_data
    return Response(
        content=audio_data,
        status_code=200
    )


@app.websocket("/assistant/azure-stt")
async def azure_stt(websocket: WebSocket):
    speech_config = speechsdk.SpeechConfig(
        subscription=AZURE_SPEECH_ACCESS_TOKEN,
        region=AZURE_SPEECH_REGION
    )
    speech_config.speech_recognition_language = AZURE_SPEECH_LANGUAGE

    # Setup the audio stream
    stream = speechsdk.audio.PushAudioInputStream()
    audio_config = speechsdk.audio.AudioConfig(stream=stream)

    # Instantiate the speech recognizer with push stream input
    speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

    result: Optional[str] = None
    stopped = False

    def recognized_cb(evt):
        nonlocal result
        result = evt.result.text

    def session_stopped_cb(evt):
        nonlocal stopped
        logger.info('Azure SESSION STOPPED: {}'.format(evt))
        stopped = True

    # Connect callbacks to the events fired by the speech recognizer
    speech_recognizer.recognizing.connect(lambda evt: logger.info(f'Azure RECOGNIZING: {evt}'))
    speech_recognizer.recognized.connect(recognized_cb)
    speech_recognizer.session_started.connect(lambda evt: logger.info(f'Azure SESSION STARTED: {evt}'))
    speech_recognizer.session_stopped.connect(session_stopped_cb)
    speech_recognizer.canceled.connect(lambda evt: logger.error(f'Azure CANCELED {evt}'))

    speech_recognizer.recognize_once_async()

    await websocket.accept()

    while not stopped:
        try:
            message = await websocket.receive()

            if 'text' in message:
                continue
            else:
                data = message['bytes']

            stream.write(data)
        except Exception as ex:
            logger.error(f"Failure during incoming websocket processing: {ex}")
            return

    await websocket.send_text(result)

aireport = Provide[Container.aireport_service]

async def aireport_updater():
    await aireport.update_context()

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = AsyncIOScheduler()
    await aireport_updater()

    scheduler.start()
    scheduler.add_job(aireport_updater, IntervalTrigger(minutes=1))
    yield
    scheduler.shutdown()

app.router.lifespan_context = lifespan

container.wire(modules=[__name__])

if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=8912)
