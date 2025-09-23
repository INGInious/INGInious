# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

from inginious.common.entrypoints import filesystem_from_config_dict

fs_provider = None

def init_fs_provider(config_fs):
    global fs_provider
    fs_provider = filesystem_from_config_dict(config_fs)

def get_fs_provider():
    return fs_provider
