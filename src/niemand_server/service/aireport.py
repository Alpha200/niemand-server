import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import reduce
from typing import Optional, List

from openai import OpenAI

from niemand_server.service.calendar import CalendarEntry, TodoEntry, CalendarService
from niemand_server.service.location import LocationService, DeviceLocation
from niemand_server.service.shopping import ShoppinglistItem, ShoppingListService
from niemand_server.service.traincheck import TrainCheckService
from niemand_server.service.weather import WeatherService


@dataclass
class Calendar:
    entries: List[CalendarEntry]
    todos: List[TodoEntry]

@dataclass
class Weather:
    forecast: str
    last_updated: datetime

@dataclass
class TrainData:
    train_status: str
    last_updated: datetime

@dataclass
class ShoppingList:
    shopping_list: List[ShoppinglistItem]

@dataclass
class ContextData:
    location: Optional[DeviceLocation]
    calender: Optional[Calendar]
    weather: Optional[Weather]
    train_status: Optional[TrainData]
    shoppinglist: Optional[ShoppingList]


class AiReportService:
    def __init__(
            self,
            openai_api_key: str,
            traccar_device_id: str,
            calendar_names: str,
            default_place: str,
            location_service: LocationService,
            calendar_service: CalendarService,
            weather_service: WeatherService,
            traincheck_service: TrainCheckService,
            shopping_list_service: ShoppingListService,
    ):
        self.client = OpenAI(api_key=openai_api_key)
        self.traccar_device_id = traccar_device_id
        self.default_place = default_place
        self.calendar_names = calendar_names.split(',')
        self.location_service = location_service
        self.calendar_service = calendar_service
        self.weather_service = weather_service
        self.traincheck_service = traincheck_service
        self.shopping_list_service = shopping_list_service
        self.logger = logging.getLogger(__name__)

        self.context_data = ContextData(
            location=None,
            calender=None,
            weather=None,
            train_status=None,
            shoppinglist=None,
        )

    async def update_context(self):
        self.logger.info(f"Updating user context")
        self.context_data.location = await self.location_service.get_device_location(self.traccar_device_id)

        entries, todos = self.calendar_service.get_upcoming_events_and_todos(self.calendar_names, 7)
        self.context_data.calender = Calendar(entries=entries, todos=todos)

        if self.context_data.weather is None or self.context_data.weather.last_updated < datetime.now() - timedelta(minutes=15):
            self.context_data.weather = Weather(
                forecast=await self.weather_service.get_forecast(self.default_place),
                last_updated=datetime.now(),
            )

        if self.context_data.train_status is None or self.context_data.train_status.last_updated < datetime.now() - timedelta(minutes=5):
            self.context_data.train_status = TrainData(
                train_status=await self.traincheck_service.check_train(),
                last_updated=datetime.now(),
            )

        self.context_data.shoppinglist = ShoppingList(
            shopping_list=await self.shopping_list_service.get_shoppinglist_items()
        )

        self.logger.info(f"Finished updating user context")

    def get_calendar_data(self) -> str:
        if self.context_data.calender is None:
            return ""

        relevant_until = datetime.combine(datetime.today(), datetime.min.time()).astimezone() + timedelta(days=2)

        def entry_is_relevant(entry) -> bool:
            begin = entry.begin.astimezone() if isinstance(entry.begin, datetime) else datetime.combine(entry.begin, datetime.min.time()).astimezone()
            return begin < relevant_until

        entries = [
            entry for entry in self.context_data.calender.entries
            if entry_is_relevant(entry)
        ]

        def todo_is_relevant(todo) -> bool:
            if todo.due is None:
                return False

            due = todo.due.astimezone() if isinstance(todo.due, datetime) else datetime.combine(todo.due, datetime.min.time()).astimezone()
            return due < relevant_until

        todos = [
            todo for todo in self.context_data.calender.todos
            if todo_is_relevant(todo)
        ]

        results = []

        if len(entries) > 0:
            results.append("Calendar: " + reduce(lambda a, b: f"{a} - {b}", (event.format() for event in entries)))

        if len(todos) > 0:
            results.append("Todo: " + reduce(lambda a, b: f"{a} - {b}", (todo.format() for todo in todos)))

        return " | ".join(results)

    def get_weather_data(self) -> str:
        if self.context_data.weather is None:
            return ""

        return self.context_data.weather.forecast

    def get_train_data(self):
        if self.context_data.train_status is None:
            return ""

        return self.context_data.train_status.train_status

    def get_shopping_data(self):
        if self.context_data.shoppinglist is None:
            return ""

        return "Shopping list: " + ", ".join([item.name for item in self.context_data.shoppinglist.shopping_list])

    def get_relevant_skill_data(self) -> str:
        data = [
            self.get_calendar_data(),
            self.get_weather_data(),
            self.get_train_data(),
            self.get_shopping_data(),
        ]
        return reduce(lambda a, b: f"{a} | {b}", (details for details in data if len(details) > 0))

    async def generate_text_report(self) -> str:
        skill_data = self.get_relevant_skill_data()

        self.logger.info(f"Generating text report for {skill_data}")

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system",
                 "content": "You assist like a caring girlfriend and answer like in a oral conversation but keep it short. Do not say you do not have anymore info and do not give advice. Answer in german. Do not say you are not trained for something. Mention the weather if it needs special clothing. Do not use emojis or formatting. Do not make up stuff."},
                {"role": "user", "content": f"Gib mir eine Übersicht über folgende Informationen ohne etwas auszulassen: {skill_data}"},
            ]
        )

        response_text = response.choices[0].message.content
        return response_text

    async def generate_voice_report(self):
        response = await self.generate_text_report()
        for chunk in self.generate_tts(response):
            yield chunk

    def generate_tts(self, text: str):
        with self.client.audio.speech.with_streaming_response.create(
                model="tts-1",
                voice="nova",
                input=text,
        ) as response:
            for chunk in response.iter_bytes():
                yield chunk
