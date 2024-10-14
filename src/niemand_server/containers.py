from dependency_injector import containers, providers
from .service.calendar import CalendarService
from .service.location import LocationService
from .service.openhab import OpenhabService
from .service.shopping import ShoppingListService
from .service.traincheck import TrainCheckService
from .service.weather import WeatherService
from .service.skill_manager import SkillManagerService
from .service.aireport import AiReportService
from .skill.openhab import OpenHABSkill
from .skill.traincheck import TraincheckSkill
from .skill.weather import WeatherSkill
from .skill.shopping import ShoppingSkill
from .skill.chatgpt import ChatGptSkill


async def provide_openhab_service(openhab_server_url, auth_token=None, lang="de"):
        openhab_service = OpenhabService(openhab_server_url, auth_token, lang)
        await openhab_service.init()
        return openhab_service

class Container(containers.DeclarativeContainer):
    config = providers.Configuration()

    # Services
    calendar_service = providers.Singleton(
        CalendarService,
        config.calendar.url,
        config.calendar.username,
        config.calendar.password,
    )

    openhab_service = providers.Resource(
        provide_openhab_service,
        config.openhab.server_url,
        config.openhab.auth_token,
        config.openhab.language,
    )

    traincheck_service = providers.Singleton(
        TrainCheckService,
        config.traincheck.station_from,
        config.traincheck.station_via,
    )

    weather_service = providers.Singleton(
        WeatherService,
    )

    location_service = providers.Singleton(
        LocationService,
        config.location.traccar_url,
        config.location.traccar_username,
        config.location.traccar_password,
    )

    shoppinglist_service = providers.Singleton(
        ShoppingListService,
        config.shopping.kitchenowl_url,
        config.shopping.kitchenowl_access_token,
        config.shopping.shoppinglist_id,
    )

    aireport_service = providers.Singleton(
        AiReportService,
        config.openai.openai_api_key,
        config.location.traccar_device_id,
        config.calendar.calendar_names,
        config.weather.default_place,
        location_service,
        calendar_service,
        weather_service,
        traincheck_service,
        shoppinglist_service,
    )

    # Skills
    openhab_skill = providers.Singleton(
        OpenHABSkill,
        openhab_service,
        config.openhab.default_room
    )

    traincheck_skill = providers.Singleton(
        TraincheckSkill,
        traincheck_service,
    )

    weather_skill = providers.Singleton(
        WeatherSkill,
        weather_service,
        config.weather.default_place
    )

    shopping_skill = providers.Singleton(
        ShoppingSkill,
    )

    chatgpt_skill = providers.Singleton(
        ChatGptSkill,
        config.openai.openai_api_key,
    )

    skill_manager = providers.Singleton(
        SkillManagerService,
        openhab_skill,
        traincheck_skill,
        weather_skill,
        shopping_skill,
        chatgpt_skill,
    )