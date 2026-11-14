from dataclasses import dataclass, field
from enum import StrEnum
from abc import ABC
import gettext
import os

from inginious import get_root_path

@dataclass(frozen=True)
class Capabilities(ABC):
    """ Capabilities translations """
    translations: dict[str, dict[str, gettext.GNUTranslations]] = field(init=False)

    def __post_init__(self):
        docs = {c: f.doc for c, f in self.__dataclass_fields__.items() if c != 'translations'}

        # Load the capabilities translations from disk.
        translations = {"en": docs}
        if self.__translation_path__:
            trad_path = os.path.join(get_root_path(), self.__translation_path__)
            available = [
                lang for lang in os.listdir(trad_path) if os.path.isdir(os.path.join(trad_path, lang))
            ]
            translations.update({
                lang: {
                    c: gettext.translation('messages', trad_path, [lang]).gettext(doc) for c, doc in docs.items()
                } for lang in available
            })
        object.__setattr__(self, 'translations', translations)

class AgentType(StrEnum):
    OCI = 'docker'
    MCQ = 'mcq'

@dataclass(frozen=True)
class GradingEnvironment:
    """ Environment hash identifier """
    id: str
    """ Creation date in epoch """
    created: int
    """ List of requested ports """
    ports: list[int]
    """ Do not propagate the environment to the frontend """
    advertised: bool = True
