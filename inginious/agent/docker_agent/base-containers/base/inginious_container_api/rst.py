# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

import os
import base64

def get_codeblock(language, text):
    """ Generates rst codeblock for given text and language """
    rst = "\n\n.. code-block:: " + language + "\n\n"
    for line in text.splitlines():
        rst += "\t" + line + "\n"

    rst += "\n"
    return rst

def get_imageblock(filename, format=''):
    """ Generates rst raw block for given image filename and format"""
    _, extension = os.path.splitext(filename)

    with open(filename, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode('utf-8')

    return '\n\n.. raw:: html\n\n\t<img src="data:image/' + (format if format else extension[1:]) + ';base64,' + encoded_string +'">\n'

def get_admonition(cssclass, title, text):
    """ Generates rst admonition block given a bootstrap alert css class, title, and text"""
    if cssclass not in ["info", "danger", "warning", "success"]:
        cssclass = "info"

    rst = ("\n\n.. admonition:: " + title + "\n") if title else "\n\n.. note:: \n"
    rst += "\t:class: alert alert-" + cssclass + "\n\n"
    for line in text.splitlines():
        rst += "\t" + line + "\n"

    rst += "\n"
    return rst

def indent_block(amount, text, indent_char='\t'):
    """ Indent (or de-indent) text"""
    rst = ""
    for line in text.splitlines():
        if amount > 0:
            rst += indent_char*amount + line + "\n"
        else:
            rst += ''.join([c for i,c in enumerate(line) if (c == indent_char and (i+1) > abs(amount)) or (not c == indent_char)]) + "\n"
    return rst
