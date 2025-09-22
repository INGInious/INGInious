# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

import gettext as _gettext
import flask
import builtins

from inginious import get_root_path
from inginious.frontend.user_manager import user_manager

def gettext(text):
    language = user_manager.session_language(default="") if flask.has_app_context() else ""
    return _translations.get(language, _gettext.NullTranslations()).gettext(text) if text else ""

_available_translations = {
    "de": "Deutsch",
    "el": "ελληνικά",
    "es": "Español",
    "fr": "Français",
    "he": "עִבְרִית",
    "nl": "Nederlands",
    "nb_NO": "Norsk (bokmål)",
    "pt": "Português",
    "vi": "Tiếng Việt"
}

available_languages = {"en": "English"}
available_languages.update(_available_translations)

_translations = {"en": _gettext.NullTranslations()} # English does not need translation ;-)
for lang in _available_translations.keys():
    _translations[lang] = _gettext.translation('messages', get_root_path() + '/frontend/i18n', [lang])

# Define _ builtin but better to explicitly import using:
# from inginious.frontend.i18n import gettext as _
builtins.__dict__['_'] = gettext