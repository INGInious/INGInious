# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.
#
# This code is based on Flask-Session, copyright (c) 2014 by Shipeng Feng.
# https://flasksession.readthedocs.io/

import re
from datetime import datetime, timezone
from bson.objectid import ObjectId

try:
    import cPickle as pickle
except ImportError:
    import pickle

from itsdangerous import Signer, BadSignature, want_bytes
from flask.sessions import SessionMixin
from werkzeug.datastructures import CallbackDict
from flask.sessions import SessionInterface
from werkzeug.exceptions import HTTPException
from inginious.frontend.pages.lti.v1_1 import LTI11LaunchPage

from inginious.frontend import database


class MongoDBSession(CallbackDict, SessionMixin):
    """Baseclass for server-side based sessions."""

    def __init__(self, initial=None, sid=None, permanent=None):
        def on_update(self):
            self.modified = True
        CallbackDict.__init__(self, initial, on_update)
        self.sid = sid
        self.modified = False
        if permanent:
            self.permanent = permanent


class MongoDBSessionInterface(SessionInterface):
    """A Session interface that uses mongodb as backend.
    :param use_signer: Whether to sign the session id cookie or not.
    :param permanent: Whether to use permanent session or not.
    """

    serializer = pickle
    session_class = MongoDBSession

    def __init__(self, use_signer=False, permanent=True):
        self.store = database.sessions
        self.store.create_index('expiration')  # ensure index
        self.use_signer = use_signer
        self.permanent = permanent

    def _generate_sid(self):
        return str(ObjectId())

    def _get_signer(self, app):
        if not app.secret_key:
            return None
        return Signer(app.secret_key, salt='flask-session',
                      key_derivation='hmac')

    def open_session(self, app, request):
        # Check for LTI session in the path
        lti_session = request.args.get('session_id')

        # Check if currently accessed URL is LTI launch pages
        try:
            # request.url_rule is not set yet here.
            endpoint, _ = app.create_url_adapter(request).match()
            is_lti_launch = endpoint == LTI11LaunchPage.endpoint
        except HTTPException:
            is_lti_launch = False

        if lti_session or is_lti_launch:
            return None

        sid = request.cookies.get(self.get_cookie_name(app))

        if not sid:
            sid = self._generate_sid()
            return self.session_class(sid=sid, permanent=self.permanent)
        if self.use_signer:
            signer = self._get_signer(app)
            if signer is None:
                return None
            try:
                sid_as_bytes = signer.unsign(sid)
                sid = sid_as_bytes.decode()
            except BadSignature:
                sid = self._generate_sid()
                return self.session_class(sid=sid, permanent=self.permanent)

        store_id = sid
        document = self.store.find_one({'_id': store_id})
        if document and document['expiration'].replace(tzinfo=timezone.utc) <= datetime.now(timezone.utc):
            # Delete expired session
            self.store.delete_one({'_id': store_id})
            document = None
        if document is not None:
            try:
                val = document['data']
                data = self.serializer.loads(want_bytes(val))
                return self.session_class(data, sid=sid)
            except:
                return self.session_class(sid=sid, permanent=self.permanent)
        return self.session_class(sid=sid, permanent=self.permanent)

    def save_session(self, app, session, response):
        domain = self.get_cookie_domain(app)
        path = self.get_cookie_path(app)
        store_id = session.sid
        if not session:
            if session.modified:
                self.store.delete_one({'_id': store_id})
                response.delete_cookie(self.get_cookie_name(app), domain=domain, path=path)
            return

        httponly = self.get_cookie_httponly(app)
        secure = self.get_cookie_secure(app)
        expires = self.get_expiration_time(app, session)
        val = self.serializer.dumps(dict(session))
        self.store.update_one({'_id': store_id},
                              {"$set": {'data': val, 'expiration': expires}},
                              upsert=True)
        if self.use_signer:
            session_id = self._get_signer(app).sign(session.sid).decode()
        else:
            session_id = session.sid
        response.set_cookie(self.get_cookie_name(app), session_id,
                            expires=expires, httponly=httponly,
                            domain=domain, path=path, secure=secure)