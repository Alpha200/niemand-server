from dataclasses import dataclass
from typing import Tuple

import aiohttp

@dataclass
class Location:
    latitude: float
    longitude: float

@dataclass
class Station:
    id: str
    name: str
    location: Location

@dataclass
class Trip:
    line: str
    direction: str
    platform: str | None
    delay: int | None
    plannedWhen: str


class TrainService:
    def __init__(self, db_rest_url: str):
        self.db_rest_url = db_rest_url

    async def get_stations(self, location: Tuple[float, float]):
        async with aiohttp.ClientSession() as session:
            url = f'{self.db_rest_url}/locations/nearby?poi=false&addresses=false&latitude={location[0]}&longitude={location[1]}'
            result = await session.get(url=url)
            result.raise_for_status()
            items = await result.json()
            return [
                Station(
                    id=item['id'],
                    name=item['name'],
                    location=Location(
                        latitude=item['location']['latitude'],
                        longitude=item['location']['longitude']
                    )
                ) for item in items
            ]

    async def get_departures(self, station_id: str):
        async with aiohttp.ClientSession() as session:
            result = await session.get(url=f'{self.db_rest_url}/stops/{station_id}/departures?duration=30')
            result.raise_for_status()
            items = (await result.json())['departures']
            return [
                Trip(
                    plannedWhen=item['plannedWhen'],
                    delay=item['delay'],
                    direction=item['direction'],
                    line=item['line']['name'],
                    platform=item['platform'],
                ) for item in items
            ]
