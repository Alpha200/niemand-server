from typing import List, Optional
from ..skill.skill import NiemandSkill, SkillResult, ProcessResponseContext
from ..skill.openhab import OpenHABSkill
from ..skill.traincheck import TraincheckSkill
from ..skill.weather import  WeatherSkill
from ..skill.shopping import ShoppingSkill
from ..skill.chatgpt import ChatGptSkill


class SkillManagerService:
    skills: List[NiemandSkill]

    def __init__(
            self,
            openhab_skill: OpenHABSkill,
            traincheck_skill: TraincheckSkill,
            weather_skill: WeatherSkill,
            shopping_skill: ShoppingSkill,
            chatgpt_skill: ChatGptSkill,
    ):
        self.skills = [
            openhab_skill,
            traincheck_skill,
            weather_skill,
            shopping_skill,
            # ChatGpt should always be the last skill (fallback)
            chatgpt_skill,
        ]

    async def run_skills(self, nlu_result: ProcessResponseContext) -> Optional[SkillResult]:
        for skill in self.skills:
            result = await skill.handle_nlu_result(nlu_result)

            if result is not None:
                return result

        return None
