from datetime import datetime


class TimeService:
    async def get_formatted_datetime(self) -> str:
        now = datetime.now()
        return f"Current date and time {now.strftime('%a %d.%m.%Y %H:%M:%S')}"
