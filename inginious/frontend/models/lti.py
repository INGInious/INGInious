# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

from mongoengine import Document, StringField, ListField, EmbeddedDocument, EmbeddedDocumentField, \
    DynamicField, DateTimeField, IntField


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

    @property
    def binding_key(self):
        """ platform_instance_id usable as a MongoDB key in User.ltibindings ('.' and '$' are forbidden) """
        return self.platform_instance_id.replace(".", "").replace("$", "")


class LaunchData(Document):
    """
    LTI launch messages and nonces, launch ids being prefixed by the LTI version (lti1p1- or lti1p3-).
    Launches are not bound to the session: LMS frames opened simultaneously without cookies each get their own session,
    and only one of them survives in the browser. They are bound to the INGInious user once logged in instead.
    """
    launch_id = StringField(required=True)  # pylti1p3 key
    value = DynamicField(required=True)
    expiration = DateTimeField(required=True)

    # Set by INGInious once the launch message is validated
    lti = EmbeddedDocumentField(LTIData)

    # Secret held by the LMS frame while no INGInious account is bound, never put in URLs. It is posted back to log in
    # once bound, and handed to the binding window, whose session differs with partitioned cookies. Unset once logged in.
    token = StringField()

    # INGInious user the launch belongs to, set once logged in: the launch is then valid
    username = StringField()

    meta = {
        'collection': 'lti_launch',
        'indexes': [
            {'fields': ['launch_id'], 'unique': True},
            {'fields': ['token'], 'sparse': True},
            {
                'fields': ['expiration'],
                'expireAfterSeconds': 0  # use field value
            }
        ]
    }


class LTIGrade(Document):
    """ Grades waiting to be sent back to the LTI platform, for both LTI versions """
    lti_version = StringField(required=True)  # "1.1" or "1.3"
    courseid = StringField()
    taskid = StringField()
    username = StringField()
    nb_attempt = IntField()

    message_launch_id = StringField()

    meta = {'collection': 'lti_grade_queue'}
