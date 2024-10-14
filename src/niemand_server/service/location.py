from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from dateutil import parser

import aiohttp


@dataclass
class DeviceLocation:
    location_time: datetime
    accuracy: int
    latitude: float
    longitude: float


class LocationService:
    def __init__(self, traccar_base_url: str, traccar_username: str, traccar_password: str):
        self.base_url = traccar_base_url
        self.auth = aiohttp.BasicAuth(traccar_username, traccar_password)

    async def get_device(self, device_id):
        async with aiohttp.ClientSession(auth=self.auth) as session:
            try:
                async with session.get(f"{self.base_url}/api/devices?id={device_id}") as response:
                    response.raise_for_status()
                    device = (await response.json())[0]
                    return device
            except aiohttp.ClientError as e:
                print(f"Error fetching device: {e}")
                return None

    async def get_position(self, position_id):
        async with aiohttp.ClientSession(auth=self.auth) as session:
            try:
                async with session.get(f"{self.base_url}/api/positions?id={position_id}") as response:
                    response.raise_for_status()
                    position = await response.json()
                    return position
            except aiohttp.ClientError as e:
                print(f"Error fetching position: {e}")
                return None

    async def get_device_location(self, device_id) -> Optional[DeviceLocation]:
        device = await self.get_device(device_id)
        if device and 'positionId' in device:
            position_id = device['positionId']
            position = await self.get_position(position_id)

            device_location = DeviceLocation(
                location_time=parser.isoparse(position[0]['deviceTime']),
                accuracy = position[0]['accuracy'],
                latitude = position[0]['latitude'],
                longitude = position[0]['longitude'],
            )

            return device_location
        else:
            print("No position ID found for the device.")
            return None