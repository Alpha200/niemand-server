import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import reduce
from typing import List

from openai import OpenAI

from niemand_server.service.calendar import CalendarEntry, TodoEntry, CalendarService
from niemand_server.service.location import LocationService, DeviceLocation
from niemand_server.service.shopping import ShoppinglistItem, ShoppingListService
from niemand_server.service.train import TrainService, Station, Trip
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
    location: DeviceLocation | None
    calender: Calendar | None
    weather: Weather | None
    train_status: TrainData | None
    shoppinglist: ShoppingList | None

@dataclass
class StructuredReport:
    train_stations: List[Station]
    trains: List[Trip]
    shopping_list: List[ShoppinglistItem]

class AiReportService:
    def __init__(
            self,
            openai_api_key: str,
            traccar_device_id: str,
            calendar_names: str,
            default_place: str,
            user_name: str,
            location_service: LocationService,
            calendar_service: CalendarService,
            weather_service: WeatherService,
            traincheck_service: TrainCheckService,
            shopping_list_service: ShoppingListService,
            train_service: TrainService,
    ):
        self.client = OpenAI(api_key=openai_api_key)
        self.traccar_device_id = traccar_device_id
        self.default_place = default_place
        self.calendar_names = calendar_names.split(',')
        self.user_name = user_name
        self.location_service = location_service
        self.calendar_service = calendar_service
        self.weather_service = weather_service
        self.traincheck_service = traincheck_service
        self.shopping_list_service = shopping_list_service
        self.train_service = train_service
        self.logger = logging.getLogger(__name__)

        self.context_data = ContextData(
            location=None,
            calender=None,
            weather=None,
            train_status=None,
            shoppinglist=None,
        )

    async def update_context(self):
        self.logger.info(f"Start updating user context")
        self.logger.info(f"Updating location context")
        self.context_data.location = await self.location_service.get_device_location(self.traccar_device_id)

        self.logger.info(f"Updating calendar context")
        entries, todos = self.calendar_service.get_upcoming_events_and_todos(self.calendar_names, 7)
        self.context_data.calender = Calendar(entries=entries, todos=todos)

        if self.context_data.weather is None or self.context_data.weather.last_updated < datetime.now() - timedelta(minutes=15):
            self.logger.info("Updating weather context")
            self.context_data.weather = Weather(
                forecast=await self.weather_service.get_forecast(self.default_place),
                last_updated=datetime.now(),
            )

        if self.context_data.train_status is None or self.context_data.train_status.last_updated < datetime.now() - timedelta(minutes=5):
            self.logger.info("Updating train context")
            self.context_data.train_status = TrainData(
                train_status=await self.traincheck_service.check_train(),
                last_updated=datetime.now(),
            )

        self.logger.info("Updating shoppinglist context")
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
            results.append("Calendar entries: " + reduce(lambda a, b: f"{a} - {b}", (event.format() for event in entries)))

        if len(todos) > 0:
            results.append("Todo list: " + reduce(lambda a, b: f"{a} - {b}", (todo.format() for todo in todos)))

        return " | ".join(results)

    def get_weather_data(self) -> str:
        if self.context_data.weather is None:
            return ""

        return self.context_data.weather.forecast

    def get_train_data(self) -> str:
        if self.context_data.train_status is None or self.context_data.location.geofence_category != 'home':
            return ""

        return self.context_data.train_status.train_status

    def get_shopping_data(self) -> str:
        if (
                self.context_data.shoppinglist is None
                or self.context_data.location is None
                or self.context_data.location.geofence_category != 'grocery-shopping'
        ):
            return ""

        if len(self.context_data.shoppinglist.shopping_list) > 0:
            return "Shopping list: " + ", ".join([item.name for item in self.context_data.shoppinglist.shopping_list])
        else:
            return "Nothing on shopping list"

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
        now_str = datetime.now().astimezone().strftime("%H:%M")

        response = self.client.chat.completions.create(
            model="gpt-4o-2024-08-06",
            messages=[
                {
                    "role": "system",
                    "content":
                        f"You assist like a warm, caring, girlfriend. Answer in natural, fluent sentences as in an oral"
                        f" conversation but keep it short. "
                        f"Do not say you do not have anymore info and do not give too much advice. Answer in german. "
                        f"Do not say you are not trained for something. Mention if the weather needs special clothing. "
                        f"Do not use emojis or formatting. Do not make up stuff and never ask questions. "
                        f"The user is named {self.user_name}, always start with a greeting. The current time is {now_str}"
                },
                {
                    "role": "user",
                    "content": f"Gib mir eine Übersicht über folgende Informationen ohne etwas auszulassen: {skill_data}"
                },
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

    async def generate_structured_report(self, parsed_location):
        if not parsed_location:
            return
        else:
            location = parsed_location

        trains = None
        train_stations = await self.train_service.get_stations(location)

        if len(train_stations) > 0:
            trains = await self.train_service.get_departures(train_stations[0].id)

        return StructuredReport(
            trains=trains,
            train_stations=train_stations,
            shopping_list=self.context_data.shoppinglist.shopping_list,
        )
