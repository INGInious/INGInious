# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

import gettext
import flask
import builtins

from inginious import get_root_path
from inginious.frontend.user_manager import user_manager

class L10nManager:

    def __init__(self):
        self.translations = {}

    def get_translation_obj(self, lang=None):
        if lang is None:
            lang = user_manager.session_language(default="") if flask.has_app_context() else ""
        return self.translations.get(lang, gettext.NullTranslations())

    def gettext(self, text):
        return self.get_translation_obj().gettext(text) if text else ""


available_translations = {
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
available_languages.update(available_translations)

# Init gettext
l10n_manager = L10nManager()
l10n_manager.translations["en"] = gettext.NullTranslations()  # English does not need translation ;-)
for lang in available_translations.keys():
    l10n_manager.translations[lang] = gettext.translation('messages', get_root_path() + '/frontend/i18n', [lang])

builtins.__dict__['_'] = l10n_manager.gettext