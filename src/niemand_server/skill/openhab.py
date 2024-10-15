import logging
from typing import List, Tuple

from genderdeterminator import GenderDeterminator, Case

from ..service.openhab import OpenhabService, Item
from .skill import NiemandSkill, SkillResult, ProcessResponseContext, get_entity_by_name, get_entities_by_name

UNKNOWN_DEVICE = "Ich habe nicht verstanden, welches Gerät du {} möchtest."
UNKNOWN_TEMPERATURE = "Die Temperatur {} ist unbekannt."
UNKNOWN_PROPERTY = "Ich habe nicht verstanden, welche Eigenschaft verändert werden soll."
FEATURE_NOT_IMPLEMENTED = "Diese Funktionalität ist aktuell nicht implementiert."


class OpenHABSkill(NiemandSkill):
    openhab: OpenhabService

    def __init__(self, openhab_service: OpenhabService, default_room: str):
        self.logger = logging.getLogger(__name__)
        self.gd = GenderDeterminator()
        self.openhab = openhab_service
        self.default_room = default_room

    def add_local_preposition(self, noun: str) -> str:
        word = self.gd.get(noun, Case.DATIVE, append=False)
        word = "im" if word == "dem" else "in der"
        return f"{word} {noun}"

    def get_items_and_room(self, context: ProcessResponseContext) -> Tuple[List[str] | None, str | None]:
        room_entity = get_entity_by_name(context.nlu.entities, 'room')
        device_entities = [entity.value for entity in get_entities_by_name(context.nlu.entities, 'device')]

        if room_entity is not None:
            room = room_entity.value
        else:
            room = None

        if not device_entities:
            device_entities = None

        return device_entities, room

    def generate_switch_result_sentence(self, devices: List[Item], command) -> str:
        if command == "ON":
            command_spoken = "eingeschaltet"
        elif command == "OFF":
            command_spoken = "ausgeschaltet"
        else:
            command_spoken = ""

        if len(devices) == 1:
            noun_with_preposition = self.gd.get(devices[0].description(), Case.ACCUSATIVE)
            return f"Ich habe dir {noun_with_preposition} {command_spoken}."
        else:
            devices_with_preposition = ", ".join(self.gd.get(device.description(), Case.ACCUSATIVE) for device in devices[:len(devices) - 1])
            last_device_with_preposition = self.gd.get(devices[len(devices) - 1].description(), Case.ACCUSATIVE)
            return f"Ich habe dir {devices_with_preposition} und {last_device_with_preposition} {command_spoken}."

    def get_room_for_current_site(self, context: ProcessResponseContext, default_room: str):
        if context.site is None:
            return default_room
        else:
            return context.site

    async def switch_on_off_action(self, context: ProcessResponseContext) -> Tuple[bool, str]:
        devices, spoken_room = self.get_items_and_room(context)

        if spoken_room is not None:
            room = self.openhab.get_location(spoken_room)

            if room is None:
                return False, f"Ich habe keinen Ort mit der Bezeichnung {spoken_room} gefunden."
        else:
            room = None

        command = "ON" if context.nlu.intent.name == "smarthome_turn_on" else "OFF"

        if devices is None:
            return False, UNKNOWN_DEVICE.format("einschalten" if command == "ON" else "ausschalten")

        relevant_devices = self.openhab.get_relevant_items(devices, room)

        # The user is allowed to omit the room if the request matches exactly one device in the users home (e.g.
        # if there is only one tv) or if the request contains only devices of the current room
        if room is None and len(relevant_devices) > 1:
            self.logger.debug("Request without room matched more than one item. Requesting again with current room.")

            spoken_room = self.get_room_for_current_site(context, self.default_room)
            room = self.openhab.get_location(spoken_room)

            relevant_devices = self.openhab.get_relevant_items(devices, room)

            if len(relevant_devices) == 0:
                return False, "Deine Anfrage war nicht eindeutig genug"

        if len(relevant_devices) == 0:
            return False, "Ich habe kein Gerät gefunden, welches zu deiner Anfrage passt"

        devices = set()

        for device in relevant_devices:
            if device.item_type in ("Switch", "Dimmer"):
                devices.add(device)
            elif device.item_type == "Group" and device.is_equipment():
                for point in device.has_points:
                    point_item = self.openhab.items[point]

                    if point_item.semantics == "Point_Control_Switch":
                        devices.add(point_item)

        await self.openhab.send_command_to_devices(devices, command)
        result_sentence = self.generate_switch_result_sentence(list(relevant_devices), command)

        return True, result_sentence

    async def handle_nlu_result(self, result: ProcessResponseContext) -> SkillResult | None:
        if not self.intent_has_global_min_confidence(result.nlu.intent):
            return None

        intent_name = result.nlu.intent.name

        if intent_name in ["smarthome_turn_on", "smarthome_turn_off"]:
            silent, response = await self.switch_on_off_action(result)
            return SkillResult(response=response)
        else:
            return None
