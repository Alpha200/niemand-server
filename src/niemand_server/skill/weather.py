from typing import Optional

from .skill import NiemandSkill, ProcessResponseContext, SkillResult, get_entity_by_name
from ..service.weather import WeatherService


class WeatherSkill(NiemandSkill):
    def __init__(self, weather_service: WeatherService, default_place: str):
        self.weather = weather_service
        self.default_place = default_place

    async def init(self):
        pass

    async def handle_nlu_result(self, result: ProcessResponseContext) -> Optional[SkillResult]:
        if not self.intent_has_global_min_confidence(result.nlu.intent):
            return None

        intent_name = result.nlu.intent.name

        if intent_name == "weather_get_forecast":
            return await self.get_weather_forecast_response(result)
        elif intent_name == "weather_get_temperature":
            temperature = await self.get_current_temperature(result)

            if temperature is not None:
                return SkillResult(response=f"Aktuell beträgt die Außentemperatur {temperature} Grad.")
            else:
                return SkillResult(response="Leider konnte ich die Außentemperatur nicht bestimmen.")

    async def get_weather_forecast_response(self, context: ProcessResponseContext):
        place = self.resolve_place(context)

        forecast = await self.weather.get_forecast(place)

        return SkillResult(response=forecast)

    def resolve_place(self, context: ProcessResponseContext) -> str:
        place = get_entity_by_name(context.nlu.entities, 'city')

        if place is None:
            return self.default_place
        else:
            return place.value

    async def get_current_temperature(self, context: ProcessResponseContext) -> str:
        place = self.resolve_place(context)
        temperature = await self.weather.get_current_temperature(place)
        return temperature