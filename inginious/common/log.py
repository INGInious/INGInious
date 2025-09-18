# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Some common functions for logging """
import logging

def init_logging(log_level=logging.DEBUG):
    """
    Init logging
    :param log_level: An integer representing the log level or a string representing one
    """
    logging.root.handlers = []  # remove possible side-effects from other libs

    # Log format
    ch = logging.StreamHandler()
    ch.setLevel(log_level)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    ch.setFormatter(formatter)

    # Base INGInious logger
    inginious_log = logging.getLogger("inginious")
    inginious_log.setLevel(log_level)
    inginious_log.addHandler(ch)

    # Allow oauthlib debug if needed to debug LTI
    oauthlib_log = logging.getLogger("oauthlib")
    oauthlib_log.setLevel(log_level)
    oauthlib_log.addHandler(ch)

    # Set werkzeug dev server log to same format to improve reading
    werkzeug_log = logging.getLogger("werkzeug")
    werkzeug_log.setLevel(log_level)
    werkzeug_log.addHandler(ch)

def get_course_logger(coursename):
    """
    :param coursename: the course id
    :return: a logger object associated to a specific course
    """
    return logging.getLogger("inginious.course."+coursename)
