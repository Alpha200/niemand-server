from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List

from pydantic import BaseModel


@dataclass
class SkillResult:
    response: str


class NluProcessResponseIntent(BaseModel):
    name: str
    confidence: float


class NluProcessEntity(BaseModel):
    entity: str
    confidence: float | None
    value: str | float | int
    extractor: str


class NluProcessResponseContext(BaseModel):
    intent: NluProcessResponseIntent
    entities: List[NluProcessEntity]


class ProcessResponseContext(BaseModel):
    nlu: NluProcessResponseContext
    utterance: str
    site: str | None


class ProcessResponse(BaseModel):
    response: str
    context: ProcessResponseContext


def map_context(result_json: dict, utterance: str, site: str) -> ProcessResponseContext:
    return ProcessResponseContext(
        nlu=NluProcessResponseContext(
            intent=NluProcessResponseIntent(
                name=result_json['intent']['name'],
                confidence=result_json['intent']['confidence'],
            ),
            entities=[
                NluProcessEntity(
                    entity=x['entity'],
                    confidence=x.get('confidence_entity', None),
                    value=x['value'],
                    extractor=x['extractor']
                )
                for x in result_json['entities']
            ]
        ),
        site=site,
        utterance=utterance
    )


def get_entity_by_name(entities: List[NluProcessEntity], name: str) -> NluProcessEntity | None:
    return next((entity for entity in entities if entity.entity == name), None)


def get_entities_by_name(entities: List[NluProcessEntity], name: str) -> List[NluProcessEntity]:
    return [entity for entity in entities if entity.entity == name]


class NiemandSkill(ABC):
    def intent_has_global_min_confidence(self, intent):
        return intent.confidence > 0.85

    @abstractmethod
    async def handle_nlu_result(self, result: ProcessResponseContext) -> SkillResult | None:
        pass
