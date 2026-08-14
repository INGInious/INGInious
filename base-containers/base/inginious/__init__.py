# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

"""
Compatibility package for legacy `inginious` imports.
Redirects submodules and attributes to `inginious_container_api`.
"""
import inginious_container_api

__path__ = list(inginious_container_api.__path__)

for _k, _v in list(inginious_container_api.__dict__.items()):
    if not _k.startswith("__"):
        globals()[_k] = _v
