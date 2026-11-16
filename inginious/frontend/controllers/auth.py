# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Authentication: auth methods registry, password hashing and user session """
import re
import logging
import hashlib
import secrets
import flask

from flask import session
from abc import ABCMeta, abstractmethod
from werkzeug.exceptions import NotFound
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from mongoengine import Q

from inginious.frontend.models import User

_auth_methods = {}
_logger = logging.getLogger("inginious.webapp.auth")


class AuthInvalidInputException(Exception):
    pass


class AuthInvalidMethodException(Exception):
    pass


class AuthMethod(object, metaclass=ABCMeta):

    @abstractmethod
    def get_id(self):
        """
        :return: The auth method id
        """
        return ""

    @abstractmethod
    def get_auth_link(self, auth_storage):
        """
        :param auth_storage: The session auth method storage dict
        :return: The authentication link
        """
        return ""

    @abstractmethod
    def callback(self, auth_storage):
        """
        :param auth_storage: The session auth method storage dict
        :return: User tuple and , or None, if failed
        """
        return None

    @abstractmethod
    def get_name(self):
        """
        :return: The name of the auth method, to be displayed publicly
        """
        return ""

    @abstractmethod
    def get_imlink(self):
        """
        :return: The image link
        """
        return ""


_email_re = re.compile(
    r"(^[-!#$%&'*+/=?^_`{}|~0-9A-Z]+(\.[-!#$%&'*+/=?^_`{}|~0-9A-Z]+)*"  # dot-atom
    r'|^"([\001-\010\013\014\016-\037!#-\[\]-\177]|\\[\001-011\013\014\016-\177])*"'  # quoted-string
    r')@(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?$', re.IGNORECASE)  # domain


def sanitize_email(email: str) -> str:
    """ Sanitize an email address and put the bar part of an address foo@bar in lower case. None if invalid. """
    if _email_re.match(email) is None:
        return None
    local, domain = email.split('@')
    return "%s@%s" % (local, domain.lower())


def hash_password_sha512(content):
    """
    :param content: a str input
    :return a hash of str input
    """
    return hashlib.sha512(content.encode("utf-8")).hexdigest()


def hash_password_argon2id(content):
    """
    :param content: a str input
    :return a hash of str input
    """
    ph = PasswordHasher()
    return ph.hash(content)


def hash_password(content):
    """
    Encapsulates the other password hashing functions
    :param content: a str input
    :return a hash of str input
    """

    methods = {"argon2id": hash_password_argon2id, "sha512": hash_password_sha512}
    latest_method = "argon2id"

    return latest_method + "-" + methods[latest_method](content)


def verify_hash(db_hash, password, method="sha512"):
    """
    Verify a hash
    :param db_hash: The hash to verify
    :param password: The password to verify
    :param method: The hash method
    :return: A boolean if the hash is correct
    """
    available_methods = {"sha512": verify_hash_sha512, "argon2id": verify_hash_argon2id}

    if method in available_methods:
        return available_methods[method](db_hash, password)
    else:
        raise AuthInvalidMethodException()


def verify_hash_sha512(db_hash, password):
    return hash_password_sha512(password) == db_hash


def verify_hash_argon2id(db_hash, password):
    try:
        ph = PasswordHasher()
        return ph.verify(db_hash, password)
    except VerifyMismatchError:
        return False


def register_auth_method(auth_method):
    """
    Registers an authentication method
    :param auth_method: an AuthMethod object
    """
    _auth_methods[auth_method.get_id()] = auth_method


def get_auth_method(auth_method_id):
    """
    :param auth_method_id: the auth method id
    :return: AuthMethod if it exists, otherwise None
    """
    return _auth_methods.get(auth_method_id, None)


def get_auth_methods():
    """
    :return: The auth methods dict
    """
    return _auth_methods


def verify_password(user, password):
    """ :return: True if the password matches the one stored for the User, False if it does not or there is none """
    if not user.password:
        return False
    method, db_hash = user.password.split("-", 1) if "-" in user.password else ("sha512", user.password)
    return verify_hash(db_hash, password, method)


def auth_user(username, password):
    """
    Authenticate an activated user using database password, and open its session
    :return: Returns a User model, or None if the authentication was not successful
    """
    user = User.objects(username=username, activate__exists=False).first()
    if user and verify_password(user, password):
        connect_user(user)
        return user


def connect_user(user):
    """ Opens a session for the user

    :param user : a User, it must at least contain the following fields:
        - realname
        - email
        - username
    """

    if not all(key in user for key in ["realname", "email", "username"]):
        raise AuthInvalidInputException()

    User.objects(email=user["email"]).update(realname=user["realname"], username=user["username"],
                                             language=user.language)

    ip = flask.request.remote_addr

    # Forge a new session to prevent session fixation
    session.regenerate()

    session.loggedin = True
    session.email = user.email
    session.username = user.username
    session.realname = user.realname
    session.language = user.language
    session.timezone = user.timezone
    session.code_indentation = user.code_indentation
    session.tos_signed = user.tos_accepted
    session.token = None

    _logger.info("User %s connected - %s - %s - %s", user["username"], user["realname"], user["email"], ip)

    return True


def disconnect_user():
    """
    Disconnects the user currently logged-in
    """
    if session.loggedin:
        ip = flask.request.remote_addr
        _logger.info("User %s disconnected - %s - %s - %s", session.username, session.realname,
                     session.email, ip)

    # Forge a new session to prevent any reuse of the previous session id (and data bound to it, like LTI launches)
    session.regenerate()


def bind_user(auth_id, user):
    """
    Add a binding method to a user
    :param auth_id: The binding method id
    :param user: (username, realname, email, additional) tuple returned by the auth method
    :return: Boolean if method has been add
    """
    username, realname, email, additional = user
    email = sanitize_email(email)
    if email is None:
        _logger.warning("Invalid email format.")
        return False

    if not get_auth_method(auth_id):
        raise NotFound(description=_("Auth method not found."))

    # Look for already bound auth method username
    user_profile = User.objects(**{"bindings__" + auth_id: username}).first()

    if user_profile and not session.loggedin:
        # Sign in
        connect_user(user_profile)
    elif user_profile and session.email == user_profile.email:
        # Logged in, refresh fields if found profile email matches session email
        user_profile.bindings[auth_id] = [username, additional]
        user_profile.save()
    elif user_profile:
        # Logged in, but already linked to another account
        _logger.warning("Tried to bind an already bound account !")
    elif session.loggedin:
        # No binding, but logged: add new binding
        # !!! Use email as it may happen that a user is logged with empty username
        # !!! if the binding link is used as is
        User.objects(email=session.email).update(**{"bindings__" + auth_id: [username, additional]})
    else:
        # No binding, check for email
        if User.objects(email=email).first():
            # Found an email, existing user account, abort without binding
            _logger.warning("The binding email is already used by another account!")
            return False
        else:
            # New user, create an account using email address
            user_profile = User(username="", realname=realname, email=email,
                                bindings={auth_id: [username, additional]}, language=session.language)

            user_profile.save()
            connect_user(user_profile)

    return True


def revoke_binding(username, binding_id):
    """
    Revoke a binding method for a user
    :param binding_id: The binding method id
    :param username: username of the user
    :return: Boolean if error occurred and message if necessary
    """
    user_data = User.objects(username=username).first()
    if binding_id not in _auth_methods:
        return True, _("Incorrect authentication binding.")
    if user_data is not None and (len(user_data.bindings.keys()) > 1 or "password" in user_data):
        User.objects(username=username).update(**{"unset__bindings__" + binding_id: 1})
        return False, ""
    return True, _("You must set a password before removing all bindings.")


def generate_token():
    """ :return: a random token, for account activation or password reset links """
    return secrets.token_hex(64)


def check_new_password(password, confirmation):
    """ :return: an error message if the new password is not acceptable, None otherwise """
    if len(password) < 6:
        return _("Password too short.")
    if password != confirmation:
        return _("Passwords don't match !")
    return None


def register_user(username, realname, email, password, language):
    """
    Create a local account, to be activated with its `activate` token
    :return: (User, None) if created, (None, error message) if the username or email is already used
    """
    existing_user = User.objects(Q(username=username) | Q(email=email)).first()
    if existing_user is not None:
        if existing_user.username == username:
            return None, _("This username is already taken !")
        return None, _("This email address is already in use !")

    user = User(username=username, realname=realname, email=email, password=hash_password(password),
                activate=generate_token(), language=language, tos_accepted=True)
    user.save()
    return user, None


def activate_user(activate_hash):
    """
    Activate a user based on his/her activation hash
    :return: True if the user was found and activated
    """
    return User.objects(activate=activate_hash).modify(unset__activate=True) is not None


def create_reset_token(email):
    """ :return: the User with this email and a new `reset` token, or None if not found """
    return User.objects(email=email).modify(reset=generate_token(), new=True)


def get_reset_user(reset_hash):
    """ :return: the User to which this reset token belongs, or None """
    return User.objects(reset=reset_hash).first()


def reset_password(reset_hash, password):
    """
    Set a new password for the user owning this reset token, and activate the account
    :return: the User, or None if the reset token is invalid
    """
    return User.objects(reset=reset_hash).modify(set__password=hash_password(password),
                                                 unset__reset=True, unset__activate=True, new=True)
