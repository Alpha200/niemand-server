from datetime import datetime

import aiohttp
from bs4 import BeautifulSoup


class WeatherService:
    async def download_weather(self, place: str) -> BeautifulSoup:
        url = f"https://www.wetteronline.de/wetter/{place}"

        async with aiohttp.ClientSession() as session:
            resp = await session.get(url)
            html_doc = await resp.text()

        return BeautifulSoup(html_doc, 'html.parser')

    async def get_forecast(self, place: str, date: datetime | None = None) -> str | None:
        soup = await self.download_weather(place)

        forecast_texts = soup.find_all("div", class_="report-text")

        idx = 0

        if date is not None and date.date() != datetime.today().date():
            idx = 1

        if len(forecast_texts) > 1:
            return forecast_texts[idx].text
        else:
            return None

    async def get_current_temperature(self, place: str) -> str:
        soup = await self.download_weather(place)
        return soup.find("div", id="nowcast-card-temperature").find("div").text
