# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

import gettext
import flask

class L10nManager:

    def __init__(self, user_manager):
        self.translations = {}
        self._user_manager = user_manager

    def get_translation_obj(self, lang=None):
        if lang is None:
            lang = self._user_manager.session_language(default="") if flask.has_app_context() else ""
        return self.translations.get(lang, gettext.NullTranslations())

    def gettext(self, text):
        return self.get_translation_obj().gettext(text) if text else ""