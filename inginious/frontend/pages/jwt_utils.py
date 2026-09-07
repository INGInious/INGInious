# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

"""
Helpers to encode/decode the API JWT tokens.

"""

import jwt

from flask import current_app


def encode_jwt(payload):
    """ Signs a JWT payload using the currently configured secret. """
    current_secret = current_app.config["API_JWT_SECRET"]
    return jwt.encode(payload, current_secret, algorithm=current_app.config["API_JWT_ALGORITHM"])


def decode_jwt(token):
    """
    Decodes a JWT, trying the current secret first, then falling back to the previously used secrets
    to support older tokens.
    """

    secrets = [current_app.config["API_JWT_SECRET"]] + current_app.config["API_JWT_OLD_SECRETS"]

    for secret in secrets:
        try:
            return jwt.decode(token, secret, algorithms=[current_app.config["API_JWT_ALGORITHM"]])
        except jwt.ExpiredSignatureError as e:
            # correct secret found, token expired
            raise e

    raise jwt.InvalidTokenError("No matching secret found")
