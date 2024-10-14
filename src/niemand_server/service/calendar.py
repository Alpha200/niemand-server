from dataclasses import dataclass
from datetime import timedelta, datetime, date
from typing import List, Optional, Union, Tuple

import caldav
from icalendar import Calendar, Event

from niemand_server.util import format_date


@dataclass
class CalendarEntry:
    summary: str
    begin: Union[datetime, date]
    end: Optional[Union[datetime, date]]

    def format(self) -> str:
        if isinstance(self.begin, datetime):
            start_text = f"Am {format_date(self.begin)}"
            end_text = f"Bis {format_date(self.end)}" if self.end is not None else ""
        else:
            if self.begin == self.end:
                start_text = f"Am {format_date(self.begin)} ganztägig"
                end_text = ""
            else:
                start_text = f"Vom {format_date(self.begin)}"
                end_text = f"Bis {format_date(self.end)}"

        return f"Titel {self.summary} {start_text} {end_text}"

@dataclass
class TodoEntry:
    summary: str
    begin: Optional[Union[datetime, date]]
    due: Optional[Union[datetime, date]]
    priority: Optional[int]
    geo: Tuple[float, float]

    def format(self) -> str:
        due_text = ""

        if self.due is not None:
            due_comp = self.due.astimezone() if isinstance(self.due, datetime) else datetime.combine(self.due, datetime.min.time()).astimezone()

            if due_comp < datetime.now().astimezone():
                due_text = "überfällig"
            else:
                due_text = f"Fällig {format_date(self.due)}"

        return f"{self.summary} {due_text}"

class CalendarService:
    client: caldav.DAVClient
    password: str

    def __init__(self, url, username, password):
        self.url = url
        self.username = username
        self.password = password

        self.client = caldav.DAVClient(url, username=username, password=password)

    def get_upcoming_events_and_todos(self, calendar_names: List[str], days_ahead):
        # Get all calendars
        calendars = self.client.principal().calendars()

        now = datetime.now()
        end_date = now + timedelta(days=days_ahead)

        events = []
        todos = []

        for calendar in calendars:
            if calendar.name not in calendar_names:
                continue

            results = calendar.search(comp_class=caldav.objects.Event, start=now, end=end_date, expand=True, split_expanded=False)

            for result in results:
                cal = Calendar.from_ical(result.data)
                for component in cal.walk():
                    if isinstance(component, Event):
                        start = component.get('dtstart')
                        end = component.get('dtend')

                        events.append(
                            CalendarEntry(
                                summary=component.get('summary'),
                                begin=start.dt if start is not None else None,
                                end=end.dt if end is not None else None,
                            )
                        )

            todo_list = calendar.todos()

            for todo in todo_list:
                if todo.icalendar_component.get('STATUS') == "NEEDS-ACTION":
                    begin = todo.icalendar_component.get('dtstart')
                    due = todo.icalendar_component.get('due')
                    geo = todo.icalendar_component.get('geo')

                    todos.append(
                        TodoEntry(
                            summary=todo.icalendar_component.get('summary'),
                            begin=begin.dt if begin is not None else None,
                            due=due.dt if due is not None else None,
                            priority=todo.icalendar_component.get('priority'),
                            geo=(geo.latitude, geo.longitude) if geo is not None else None,
                        )
                    )

        return events, todos