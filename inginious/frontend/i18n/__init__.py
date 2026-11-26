# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

import gettext as _gettext
import flask
import builtins

from flask import session
from inginious import get_root_path

def gettext(text):
    language = session.language if flask.has_app_context() else ""
    return _translations.get(language, _gettext.NullTranslations()).gettext(text) if text else ""

def pgettext(context, text):
    language = session.language if flask.has_app_context() else ""
    translations = _translations.get(language, _gettext.NullTranslations())
    return translations.pgettext(context, text) if text else ""

available_languages = ["en", "de", "el", "es", "fr", "he", "nl", "nb_NO", "pl", "pt", "vi"]
_regional_variants = ["de_AT", "de_BE", "de_CH", "de_DE", "el_CY", "el_GR", "en_AU", "en_CA", "en_GB", "en_IE", "en_US",
                      "es_AR", "es_ES", "es_MX", "fr_BE", "fr_CA", "fr_CH", "fr_FR", "fr_LU", "he_IL", "nl_BE", "nl_NL",
                      "pl_PL", "pt_BR", "pt_PT", "vi_VN"]
available_locales = sorted(available_languages + _regional_variants)

# gettext falls back on ll when no ll_CC catalog exists, and on NullTranslations for English
_translations = {lang: _gettext.translation('messages', get_root_path() + '/frontend/i18n', [lang], fallback=True)
                 for lang in available_locales}

# Define _ builtin but better to explicitly import using:
# from inginious.frontend.i18n import gettext as _
builtins.__dict__['_'] = gettext