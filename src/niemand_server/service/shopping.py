from dataclasses import dataclass

import aiohttp

@dataclass
class ShoppinglistItem:
    name: str

class ShoppingListService:
    def __init__(self, kitchenowl_url: str, kitchenowl_access_token: str, shoppinglist_id: str):
        self.kitchenowl_url = kitchenowl_url
        self.shoppinglist_id = shoppinglist_id

        self.headers = {
            'Authorization': f'Bearer {kitchenowl_access_token}'
        }

    async def get_shoppinglist_items(self):
        async with aiohttp.ClientSession(headers=self.headers) as session:
            payload = dict(

            )
            result = await session.get(url=f'{self.kitchenowl_url}/api/shoppinglist/{self.shoppinglist_id}/items', json=payload)
            result.raise_for_status()
            items = await result.json()
            return [ShoppinglistItem(item['name']) for item in items]