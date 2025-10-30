# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.
#
# This code is based on Flask-Session, copyright (c) 2014 by Shipeng Feng.
# https://flasksession.readthedocs.io/

from datetime import datetime, timezone

from itsdangerous import Signer, BadSignature
from flask.sessions import SessionInterface
from werkzeug.exceptions import HTTPException
from inginious.frontend.pages.lti.v1_1 import LTI11LaunchPage

from inginious.frontend.models.session import Session


class MongoDBSessionInterface(SessionInterface):
    """A Session interface that uses mongodb as backend.
    :param use_signer: Whether to sign the session id cookie or not.
    :param permanent: Whether to use permanent session or not.
    """

    def __init__(self, use_signer=False, permanent=True):
        self.use_signer = use_signer
        self.permanent = permanent

    def _get_signer(self, app):
        if not app.secret_key:
            return None
        return Signer(app.secret_key, salt='flask-session', key_derivation='hmac')

    def open_session(self, app, request):
        # Check for LTI session in the path
        lti_session = request.args.get('session_id')

        # If LTI launch page, then generate a new LTI session
        try:
            # request.url_rule is not set yet here.
            endpoint, _ = app.create_url_adapter(request).match()
            if endpoint == LTI11LaunchPage.endpoint:
                return Session(permanent=self.permanent, is_lti=True)
        except HTTPException:
            pass # Could not determine endpoint, continue

        sid = lti_session or request.cookies.get(self.get_cookie_name(app))

        if not sid:
            return Session(permanent=self.permanent)

        if self.use_signer and not lti_session:
            signer = self._get_signer(app)
            if signer is None:
                return None
            try:
                sid_as_bytes = signer.unsign(sid)
                sid = sid_as_bytes.decode()
            except BadSignature:
                return Session(permanent=self.permanent)

        document = Session.objects(id=sid).first()
        if document and document.expiration <= datetime.now(timezone.utc):
            # Delete expired session
            document.delete()
            document = None
        return document or Session(permanent=self.permanent)

    def save_session(self, app, session, response):
        expires = self.get_expiration_time(app, session)
        session.expiration = expires
        session.save()

        if not session.is_lti:
            session_id = self._get_signer(app).sign(str(session.id)).decode() if self.use_signer else session.id
            domain = self.get_cookie_domain(app)
            path = self.get_cookie_path(app)
            httponly = self.get_cookie_httponly(app)
            secure = self.get_cookie_secure(app)
            response.set_cookie(self.get_cookie_name(app), session_id, expires=expires, httponly=httponly,
                                domain=domain, path=path, secure=secure)