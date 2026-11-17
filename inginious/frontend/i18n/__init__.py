# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

import gettext as _gettext
import re
import flask
import builtins

from flask import session
from inginious import get_root_path
from inginious.common.base import get_translation

def gettext(text):
    language = session.language if flask.has_app_context() else ""
    return get_translation(_translations, language).gettext(text) if text else ""

def pgettext(context, text):
    language = session.language if flask.has_app_context() else ""
    return get_translation(_translations, language).pgettext(context, text) if text else ""

def normalize_language(code):
    """ Returns the gettext ll or ll_CC form (ISO 639-1 language, ISO 3166 country) of a language tag such as fr,
        fr-BE or fr_be, or None if the language is not supported or the country is not a 2-letter code """
    lang, _, country = (code or "").replace("-", "_").partition("_")
    lang, country = lang.lower(), country.upper()
    if lang not in available_languages or (country and not re.fullmatch("[A-Z]{2}", country)):
        return None
    return f"{lang}_{country}" if country else lang

_available_translations = {
    "de": "Deutsch",
    "el": "ελληνικά",
    "es": "Español",
    "fr": "Français",
    "he": "עִבְרִית",
    "nl": "Nederlands",
    "nb_NO": "Norsk (bokmål)",
    "pl": "Polski",
    "pt": "Português",
    "vi": "Tiếng Việt"
}

# Languages are identified by their ISO 639-1 code, the country is chosen separately
available_languages = {"en": "English"}
available_languages.update({lang.split("_")[0]: name for lang, name in _available_translations.items()})

_translations = {"en": _gettext.NullTranslations()} # English does not need translation ;-)
for lang in _available_translations.keys():
    _translations[lang] = _gettext.translation('messages', get_root_path() + '/frontend/i18n', [lang])
    _translations.setdefault(lang.split("_")[0], _translations[lang]) # e.g. nb_NO is also used for nb_BE

# Define _ builtin but better to explicitly import using:
# from inginious.frontend.i18n import gettext as _
builtins.__dict__['_'] = gettext
