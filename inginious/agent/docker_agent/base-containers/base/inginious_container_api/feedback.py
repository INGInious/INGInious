# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

import json
import os
import traceback

from jinja2 import Template

from inginious_container_api.input import get_lang
import inginious_container_api.lang

_feedback_dir = '/.__output' if not inginious_container_api.DEBUG else './'
_feedback_file = os.path.join(_feedback_dir, '__feedback.json')

def _load_feedback():
    """ Open existing feedback file """
    result = {}
    if os.path.exists(_feedback_file):
        f = open(_feedback_file, 'r')
        cont = f.read()
        f.close()
    else:
        cont = '{}'

    try:
        result = json.loads(cont) if cont else {}
    except ValueError as e:
        result = {"result":"crash", "text":"Feedback file has been modified by user !"}
    return result


def save_feedback(rdict):
    """ Save feedback file """
    # Check for output folder
    if not os.path.exists(_feedback_dir):
        os.makedirs(_feedback_dir)
    
    jcont = json.dumps(rdict)
    f = open(_feedback_file, 'w')
    f.write(jcont)
    f.close()


# Doing the real stuff
def set_global_result(result):
    """ Set global result value """
    rdict = _load_feedback()
    rdict['result'] = result
    save_feedback(rdict)


def set_problem_result(result, problem_id):
    """ Set problem specific result value """
    rdict = _load_feedback()
    if not 'problems' in rdict:
        rdict['problems'] = {}
    cur_val = rdict['problems'].get(problem_id, '')
    rdict['problems'][problem_id] = [result, cur_val] if type(cur_val) == str else [result, cur_val[1]]
    save_feedback(rdict)


def set_grade(grade):
    """ Set global grade of this job """
    rdict = _load_feedback()
    rdict['grade'] = float(grade)
    save_feedback(rdict)


def set_global_feedback(feedback, append=False):
    """ Set global feedback in case of error """
    if not isinstance(feedback, str):
        raise ValueError("Feedback doesn't match correct instance")
    rdict = _load_feedback()
    rdict['text'] = rdict.get('text', '') + feedback if append else feedback
    save_feedback(rdict)


def set_problem_feedback(feedback, problem_id, append=False):
    """ Set problem specific feedback """
    if not isinstance(feedback, str):
        raise ValueError("Feedback doesn't match correct instance")
    rdict = _load_feedback()
    if not 'problems' in rdict:
        rdict['problems'] = {}
    cur_val = rdict['problems'].get(problem_id, '')
    rdict['problems'][problem_id] = (cur_val + feedback if append else feedback) if type(cur_val) == str else [cur_val[0], (cur_val[1] + feedback if append else feedback)]
    save_feedback(rdict)



def set_state(state):
    """ Set the task state """
    rdict = _load_feedback()
    rdict['state'] = state
    save_feedback(rdict)


def set_tag(tag, value):
    """ 
    Set the tag 'tag' to the value True or False. 
    :param value: should be a boolean
    :param tag: should be the id of the tag. Can not starts with ``*auto-tag-``
    """ 
    if not tag.startswith("*auto-tag-"):
        rdict = _load_feedback()
        tests = rdict.setdefault("tests", {})
        tests[tag] = (value == True)
        save_feedback(rdict)
        
def tag(value):
    """
    Add a tag with generated id.
    :param value: everything working with the str() function
    """
    rdict = _load_feedback()
    tests = rdict.setdefault("tests", {})
    tests["*auto-tag-" + str(hash(str(value)))] = str(value)
    save_feedback(rdict)

def set_custom_value(custom_name, custom_val):
    """
    Set a custom value to be given back in the feedback
    :param custom_name: name/key of the entry to be placed in the custom dict
    :param custom_val: content of the entry to be placed in the custom dict
    """
    rdict = _load_feedback()
    if not "custom" in rdict:
        rdict["custom"] = {}
    rdict["custom"][custom_name] = custom_val
    save_feedback(rdict)


def get_feedback():
    """ Returns the dictionary containing the feedback """
    rdict = _load_feedback()
    return rdict


def set_feedback_from_tpl(tpl_name, parameters, problem_id=None, append=False):
    """ Parse a template, using the given parameters, and set it as the feedback message.

        tpl_name must indicate a file. Given that XX_XX is the lang code of the current user ('en_US' or 'fr_FR', for example),
        this function will search template file in different locations, in the following order:
        - [current_dir]/tpl_name.XX_XX.tpl
        - [task_dir]/lang/XX_XX/tpl_name.tpl (this is the preferred way, as it contributes to store all translations in the same folder)
        - [current_dir]/tpl_name.tpl

        Note that you can indicate "../otherdir/mytpl" to force the function to search in the "../otherdir" directory. Simply omit the final ".tpl".

        If no file is found or a parsing exception occured, an error is displayed as feedback message, and False is returned.
        If everything went well, True is returned.

        The parsing uses Jinja2.

        Parameters is a dictionnary that will be given to the Jinja template.
    """
    inginious_container_api.lang.init()
    lang = get_lang()

    tpl_location = None
    possible_locations = [".".join([tpl_name, lang, "tpl"]),
                          os.path.join(inginious_container_api.lang.get_lang_dir_path(), lang, tpl_name) + ".tpl",
                          ".".join([tpl_name, "tpl"])]
    for path in possible_locations:
        if os.path.exists(path):
            tpl_location = path
            break

    if tpl_location is None:
        output = """
.. error::

    Unable to find template named %s. Please contact your administrator.
    

    """ % tpl_name

        if problem_id is None:
            set_global_feedback(output, append)
        else:
            set_problem_feedback(output, problem_id, append)
        return False

    try:
        template = Template(open(tpl_location, 'r').read())
        parameters.update({"_": _})
        output = template.render(parameters)
        valid = True
    except Exception:
        output = """
.. error::
   
   An error occured while parsing the feedback template. Here is the full error:
   
   ::
   
"""
        output += "\n".join(["\t\t"+line for line in traceback.format_exc().split("\n")])
        output += "\n\tPlease contact your administrator.\n"
        valid = False

    if problem_id is None:
        set_global_feedback(output, append)
    else:
        set_problem_feedback(output, problem_id, append)

    return valid


