# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Babel extractors for INGInious files """

from inginious.common import custom_yaml
from inginious.common.tasks_problems import Problem, get_problem_types

def import_class(name):
    m = name.split('.')
    mod = __import__(m[0])

    for comp in m[1:]:
        mod = getattr(mod, comp)
    return mod

def get_strings(content, fields):
    # If fields is an empty list or dict, take all the elements
    if isinstance(fields, dict) and not len(fields):
        for key, val in content.items():
            yield val, key
    elif isinstance(fields, list) and not len(fields):
        for val in content:
            yield val, ""

    for key, val in fields.items():
        if isinstance(val, dict):
            yield from get_strings(content.get(key, {}), val)
        elif isinstance(val, list):
            for elem in content.get(key, []):
                yield from get_strings(elem, val[0])
        else:
            result = content.get(key, "")
            if result:
                yield result, key


def extract_yaml(fileobj, keywords, comment_tags, options):
    task_problem_types = get_problem_types()

    problems = options["problems"].split() if "problems" in options else []
    for problem in problems:
        problem_class = import_class(problem)
        task_problem_types[problem_class.get_type()] = problem_class

    source = fileobj.read().decode(options.get('encoding', 'utf-8'))
    content = custom_yaml.load(source)

    if "task.yaml" in fileobj.name:
        keys = ["author", "context", "name"]
        for key in keys:
            yield 0, "", content.get(key, ""), [key]

        for problem_id, problem_content in content.get("problems").items():
            fields = task_problem_types.get(problem_content.get('type', ""), Problem).get_text_fields()

            for string, strkey in get_strings(content.get("problems").get(problem_id), fields):
                yield 0, "", string, [key + ", " + problem_id + ", " + strkey]

    elif "course.yaml" in fileobj.name:
        yield 0, "", content.get("name", ""), ["name"]

