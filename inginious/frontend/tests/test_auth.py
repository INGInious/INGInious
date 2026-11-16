# pylint: disable=redefined-outer-name
# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Tests for the auth controller. They need a MongoDB server on localhost, and are skipped otherwise. """

import re
import time
from datetime import datetime, timedelta

import flask
import jwt
import pytest
from mongoengine import ValidationError, connect, disconnect
from pymongo.errors import PyMongoError

from inginious.frontend.controllers import auth
from inginious.frontend.flask.mongo_sessions import MongoDBSessionInterface
from inginious.frontend.models import User, Session, LaunchData, LTIData
from inginious.frontend.pages.utils import auth_error_message

TEST_DB = "INGInious_test_auth"
JWT_SECRET = "a-test-secret-long-enough-for-hs256-signatures"


class DummyAuthMethod(auth.AuthMethod):
    def __init__(self, id):
        self._id = id

    def get_id(self):
        return self._id

    def get_auth_link(self, auth_storage):
        return "/dummy"

    def callback(self, auth_storage):
        return None

    def get_name(self):
        return "Dummy"

    def get_imlink(self):
        return ""


@pytest.fixture(scope="module")
def db():
    client = connect(TEST_DB, host="mongodb://localhost:27017", tz_aware=True, serverSelectionTimeoutMS=2000)
    try:
        client.admin.command("ping")
    except PyMongoError:
        disconnect()
        pytest.skip("No MongoDB server available on localhost")
    yield
    client.drop_database(TEST_DB)
    disconnect()


@pytest.fixture(autouse=True)
def clean(db, monkeypatch):
    """ Empty collections and auth methods registry before each test """
    for model in (User, Session, LaunchData):
        model.drop_collection()
    monkeypatch.setattr(auth, "_auth_methods", {})


@pytest.fixture(autouse=True)
def session(db):
    """
    Runs each test in a request context, as in the webapp: the session, the app config and the translations
    (once inginious.frontend.i18n is imported) need one. Returns the (INGInious) session.
    """
    app = flask.Flask(__name__)
    app.secret_key = "test"
    app.config["API_JWT_SECRET"] = JWT_SECRET
    app.session_interface = MongoDBSessionInterface(False, True)
    with app.test_request_context(environ_base={"REMOTE_ADDR": "127.0.0.1"}):
        yield flask.session


def make_user(username="alice", password=None, **kwargs):
    kwargs.setdefault("email", username + "@example.com")
    kwargs.setdefault("realname", username.capitalize())
    if password is not None:
        kwargs["password"] = auth.hash_password(password)
    user = User(username=username, **kwargs)
    user.save()
    return user


def make_lti(username, platform="https://lms.example.com/client/deployment"):
    return LTIData(version="1.3", username=username, platform_instance_id=platform, redir_url="/task")


def make_launch(lti):
    launch = LaunchData(launch_id="launch-" + lti.username, value={}, expiration=datetime.now() + timedelta(hours=1),
                        lti=lti, token="launch-token")
    launch.save()
    return launch


#########################
# Hashing and helpers   #
#########################

def test_hash_password_uses_argon2id():
    hashed = auth.hash_password("secret")
    method, db_hash = hashed.split("-", 1)
    assert method == "argon2id"
    assert auth.verify_hash(db_hash, "secret", method)
    assert not auth.verify_hash(db_hash, "other", method)


def test_verify_hash_legacy_sha512():
    db_hash = auth.hash_password_sha512("secret")
    assert auth.verify_hash(db_hash, "secret")
    assert not auth.verify_hash(db_hash, "other")


def test_verify_hash_sha512_malformed_hash():
    assert not auth.verify_hash("non-ascii-hash-é", "secret")


def test_verify_hash_unknown_method():
    with pytest.raises(auth.AuthInvalidMethodException):
        auth.verify_hash("hash", "secret", "md5")


@pytest.mark.parametrize("email, expected", [
    ("Foo@BAR.com", "Foo@bar.com"),
    ("first.last@sub.example.org", "first.last@sub.example.org"),
    ("not-an-email", None),
    ("missing@tld", None),
])
def test_sanitize_email(email, expected):
    assert auth.sanitize_email(email) == expected


def test_check_new_password():
    auth.check_new_password("abcdef", "abcdef")
    with pytest.raises(auth.PasswordTooShort):
        auth.check_new_password("abcde", "abcde")
    with pytest.raises(auth.PasswordMismatch):
        auth.check_new_password("abcdef", "abcdeg")


@pytest.mark.parametrize("error", [cls for cls in auth.AuthError.__subclasses__()
                                   if cls not in (auth.AuthInvalidInputException, auth.AuthInvalidMethodException)])
def test_auth_errors_have_a_message(error):
    """ Errors pages may receive from the auth controller have a specific message """
    assert auth_error_message(error()) != auth_error_message(auth.AuthError())


def test_generate_token():
    token = auth.generate_token()
    assert re.fullmatch(r"[0-9a-f]{128}", token)
    assert token != auth.generate_token()


def test_auth_methods_registry():
    method = DummyAuthMethod("dummy")
    auth.register_auth_method(method)
    assert auth.get_auth_method("dummy") is method
    assert auth.get_auth_method("unknown") is None
    assert auth.get_auth_methods() == {"dummy": method}


#########################
# Local accounts        #
#########################

def test_verify_password():
    assert auth.verify_password(make_user("alice", "secret"), "secret")
    assert not auth.verify_password(make_user("bob", "secret"), "other")
    assert not auth.verify_password(make_user("carol"), "")


def test_register_activate_and_login(session):
    user = auth.register_user("alice", "Alice", "alice@example.com", "secret", "fr")
    assert user.activate
    assert user.tos_accepted and user.language == "fr"

    # Accounts must be activated before logging in
    assert auth.auth_user("alice", "secret") is None
    assert not session.loggedin

    assert auth.activate_user(user.activate)
    assert not auth.activate_user(user.activate)

    assert auth.auth_user("alice", "wrong") is None
    assert auth.auth_user("alice", "secret").username == "alice"
    assert session.loggedin and session.username == "alice" and session.language == "fr"


def test_register_user_already_used():
    make_user("alice")
    with pytest.raises(auth.UsernameTaken):
        auth.register_user("alice", "A", "other@example.com", "secret", "en")
    with pytest.raises(auth.EmailTaken):
        auth.register_user("bob", "B", "alice@example.com", "secret", "en")
    assert User.objects.count() == 1


def test_password_reset():
    make_user("alice", "old-password", activate="pending")
    assert auth.create_reset_token("unknown@example.com") is None

    reset_hash = auth.create_reset_token("alice@example.com").reset
    assert reset_hash
    assert auth.get_reset_user(reset_hash).username == "alice"
    assert auth.get_reset_user("invalid") is None

    assert auth.reset_password(reset_hash, "new-password").username == "alice"
    user = User.objects.get(username="alice")
    assert user.reset is None and user.activate is None  # resetting also activates the account
    assert auth.verify_password(user, "new-password")
    assert auth.reset_password(reset_hash, "again") is None  # token can only be used once


@pytest.mark.parametrize("empty_hash", [None, ""])
def test_empty_tokens_match_no_account(empty_hash):
    """ Accounts without pending activation or reset must not match an empty token """
    make_user("alice", "secret")
    assert not auth.activate_user(empty_hash)
    assert auth.get_reset_user(empty_hash) is None
    assert auth.reset_password(empty_hash, "hijacked") is None
    assert auth.verify_password(User.objects.get(username="alice"), "secret")


#########################
# Sessions and bindings #
#########################

def test_connect_and_disconnect_regenerate_session(session):
    session.save()
    anonymous_id = session.id

    auth.connect_user(make_user("alice", tos_accepted=True))
    assert session.id != anonymous_id  # prevents session fixation
    assert session.loggedin and session.username == "alice" and session.tos_signed

    logged_id = session.id
    auth.disconnect_user()
    assert session.id != logged_id
    assert not session.loggedin and session.username is None


def test_connect_user_does_not_write_user(session):
    stale = make_user("alice")
    User.objects(username="alice").update(realname="Alice Updated")
    auth.connect_user(stale)
    assert User.objects.get(username="alice").realname == "Alice Updated"


def test_bind_user_unknown_method(session):
    with pytest.raises(auth.UnknownAuthMethod):
        auth.bind_user("unknown", auth.AuthUserInfo("ext", "Alice", "alice@example.com", {}))


def test_bind_user_invalid_email(session):
    auth.register_auth_method(DummyAuthMethod("dummy"))
    assert not auth.bind_user("dummy", auth.AuthUserInfo("ext", "Alice", "not-an-email", {}))
    assert User.objects.count() == 0


def test_bind_user_creates_account(session):
    auth.register_auth_method(DummyAuthMethod("dummy"))
    assert auth.bind_user("dummy", auth.AuthUserInfo("ext", "Alice", "alice@EXAMPLE.com", {"k": "v"}))
    user = User.objects.get(email="alice@example.com")
    assert user.bindings == {"dummy": ["ext", {"k": "v"}]}
    assert session.loggedin and session.email == "alice@example.com"


def test_bind_user_logs_in_bound_account(session):
    auth.register_auth_method(DummyAuthMethod("dummy"))
    make_user("alice", bindings={"dummy": ["ext", {}]})
    assert auth.bind_user("dummy", auth.AuthUserInfo("ext", "Alice", "changed@example.com", {}))
    assert session.loggedin and session.username == "alice"


def test_bind_user_refuses_existing_unbound_email(session):
    auth.register_auth_method(DummyAuthMethod("dummy"))
    make_user("alice")
    assert not auth.bind_user("dummy", auth.AuthUserInfo("ext", "Alice", "alice@example.com", {}))
    assert User.objects.get(username="alice").bindings == {}
    assert not session.loggedin


def test_bind_user_adds_binding_to_logged_in_user(session):
    auth.register_auth_method(DummyAuthMethod("dummy"))
    auth.connect_user(make_user("alice"))
    assert auth.bind_user("dummy", auth.AuthUserInfo("ext", "Alice", "other@example.com", {}))
    assert User.objects.get(username="alice").bindings == {"dummy": ["ext", {}]}


def test_bind_user_keeps_binding_of_another_account(session):
    auth.register_auth_method(DummyAuthMethod("dummy"))
    make_user("bob", bindings={"dummy": ["ext", {}]})
    auth.connect_user(make_user("alice"))
    auth.bind_user("dummy", auth.AuthUserInfo("ext", "Alice", "alice@example.com", {}))
    assert User.objects.get(username="alice").bindings == {}
    assert User.objects.get(username="bob").bindings == {"dummy": ["ext", {}]}
    assert session.username == "alice"


def test_revoke_binding():
    auth.register_auth_method(DummyAuthMethod("dummy"))
    make_user("alice", bindings={"dummy": ["ext", {}]})
    make_user("bob", "secret", bindings={"dummy": ["ext2", {}]})

    with pytest.raises(auth.UnknownAuthMethod):
        auth.revoke_binding("alice", "unknown")
    # The last binding of an account without password cannot be removed
    with pytest.raises(auth.LastBindingWithoutPassword):
        auth.revoke_binding("alice", "dummy")
    auth.revoke_binding("bob", "dummy")
    assert User.objects.get(username="bob").bindings == {}


#########################
# LTI                   #
#########################

def test_bind_lti():
    for username in ("alice", "bob", "carol"):
        make_user(username)

    other_platform = make_lti("lti-2", platform="https://other-lms.example.com/c/d")
    assert auth.bind_lti("alice", make_lti("lti-1"))
    assert auth.bind_lti("alice", make_lti("lti-1"))  # already bound to this account
    assert not auth.bind_lti("bob", make_lti("lti-1"))  # LTI user bound to another account
    assert not auth.bind_lti("alice", make_lti("lti-2"))  # account bound to another LTI user
    assert auth.bind_lti("alice", other_platform)

    assert User.objects.get(username="alice").ltibindings == {
        make_lti("lti-1").binding_key: "lti-1",
        other_platform.binding_key: "lti-2",
    }
    assert User.objects.get(username="bob").ltibindings == {}


def test_lti_login(session):
    unbound = make_launch(make_lti("lti-unbound"))
    assert auth.lti_login(unbound) is None
    assert not session.loggedin

    make_user("alice")
    auth.bind_lti("alice", make_lti("lti-1"))
    launch = make_launch(make_lti("lti-1"))
    assert auth.lti_login(launch).username == "alice"
    assert session.loggedin and session.username == "alice"
    launch.reload()
    assert launch.username == "alice" and launch.token is None


#########################
# API tokens and keys   #
#########################

def test_api_tokens():
    user = make_user("alice")
    token = auth.create_api_token(user, 10, "CI")
    token_id, stored = next(iter(User.objects.get(username="alice").apitokens.items()))
    assert stored.description == "CI" and stored.token.startswith("argon2id-")
    assert auth.verify_api_token(token).username == "alice"

    user.reload()
    assert not auth.revoke_api_token(user, "unknown")
    assert auth.revoke_api_token(user, token_id)
    assert User.objects.get(username="alice").apitokens == {}
    with pytest.raises(jwt.InvalidTokenError):
        auth.verify_api_token(token)


def test_create_api_token_invalid_description():
    with pytest.raises(ValidationError):
        auth.create_api_token(make_user("alice"), 10, "")


@pytest.mark.parametrize("secret, sub, expires_in, error", [
    (JWT_SECRET, "alice", -60, jwt.ExpiredSignatureError),
    ("another-secret-long-enough-for-hs256-signatures", "alice", 60, jwt.InvalidSignatureError),
    (JWT_SECRET, "unknown", 60, jwt.InvalidTokenError),
])
def test_verify_api_token_invalid(secret, sub, expires_in, error):
    make_user("alice")
    token = jwt.encode({"jti": "id", "sub": sub, "exp": time.time() + expires_in}, secret, algorithm="HS256")
    with pytest.raises(error):
        auth.verify_api_token(token)


def test_verify_api_token_malformed():
    with pytest.raises(jwt.DecodeError):
        auth.verify_api_token("not-a-jwt")


def test_get_api_key():
    make_user("alice")
    make_user("bob", apikey="existing-key")

    key = auth.get_api_key("alice")
    assert re.fullmatch(r"[0-9a-f]{80}", key)
    assert auth.get_api_key("alice") == key
    assert auth.get_api_key("bob") == "existing-key"
    assert auth.get_api_key("unknown") is None
