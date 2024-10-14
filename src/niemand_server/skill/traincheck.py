from typing import Optional

from .skill import NiemandSkill, SkillResult, ProcessResponseContext
from ..service.traincheck import TrainCheckService


class TraincheckSkill(NiemandSkill):
    def __init__(self, traincheck_service: TrainCheckService):
        self.traincheck = traincheck_service

    async def init(self):
        pass

    async def handle_nlu_result(self, result: ProcessResponseContext) -> Optional[SkillResult]:
        if not self.intent_has_global_min_confidence(result.nlu.intent):
            return None

        intent_name = result.nlu.intent.name

        if intent_name == "traincheck_check_train":
            response = await self.traincheck.check_train()
            return SkillResult(response=response)
        else:
            return None