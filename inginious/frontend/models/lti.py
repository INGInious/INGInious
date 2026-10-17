# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

from mongoengine import StringField, ListField, EmbeddedDocument


class LTIData(EmbeddedDocument):
    """ User and context information extracted from a LTI launch message """
    version = StringField(required=True, default="")
    email = StringField(required=True, default="")
    username = StringField(required=True, default="")
    realname = StringField(required=True, default="")
    roles = ListField(StringField())
    task = ListField(StringField(), required=True, default=lambda: ['', ''])
    redir_url = StringField(required=True, default="")

    # LTI1.1: courseid/consumer key, LTI1.3: issuer/client_id/deployment_id
    platform_instance_id = StringField(required=True)

    context_title = StringField()
    context_label = StringField()
    tool_description = StringField()
    tool_name = StringField()
    tool_url = StringField()
