import os
from .skill import NiemandSkill, SkillResult, ProcessResponseContext, get_entity_by_name
from ..service.shopping import ShoppingListService


class ShoppingSkill(NiemandSkill):

    def __init__(self):
        tandoor_server_url = os.environ.get("TANDOOR_SERVER_URL")
        tandoor_access_token = os.environ.get("TANDOOR_ACCESS_TOKEN")
        self.shopping = ShoppingListService(tandoor_server_url, tandoor_access_token)

    async def init(self):
        pass

    async def handle_nlu_result(self, result: ProcessResponseContext) -> SkillResult | None:
        if not self.intent_has_global_min_confidence(result.nlu.intent):
            return None

        intent_name = result.nlu.intent.name

        if intent_name == "shopping_list_add_item":
            result = await self.add_shopping_list_item(result)
            return SkillResult(response=result)
        else:
            return None

    async def add_shopping_list_item(self, context: ProcessResponseContext) -> str:
        unit_entity = get_entity_by_name(context.nlu.entities, 'shopping_list_unit')
        item_entity = get_entity_by_name(context.nlu.entities, 'shopping_list_item')
        amount_entity = get_entity_by_name(context.nlu.entities, 'number')

        if item_entity is None:
            return "Ich habe nicht verstanden was du auf die Einkaufsliste schreiben möchtest"

        await self.shopping.add_item_to_shopping_list(
            item_entity.value,
            unit_entity.value if unit_entity is not None else None,
            amount_entity.value if amount_entity is not None else None
        )

        return f'Ich habe dir ' \
               f'{amount_entity.value if amount_entity is not None else ""} ' \
               f'{unit_entity.value if unit_entity is not None else ""} ' \
               f'{item_entity.value} auf die Einkaufsliste geschrieben'
