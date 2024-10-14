import os
from typing import Optional

from openai import OpenAI
from .skill import NiemandSkill, SkillResult, ProcessResponseContext


class ChatGptSkill(NiemandSkill):
    client: OpenAI

    def __init__(self, openai_api_key: str):
        self.client = OpenAI(api_key=openai_api_key)

    async def handle_nlu_result(self, result: ProcessResponseContext) -> Optional[SkillResult]:
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful voice assistant that answers in german and gives compact but meaningful answers."},
                {"role": "user", "content": result.utterance},
            ]
        )

        return SkillResult(response=response.choices[0].message.content)
