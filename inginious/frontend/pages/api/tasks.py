# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Tasks """

from inginious.frontend.pages.api._api_page import APIAuthenticatedPage, APINotFound, APIForbidden
from inginious.frontend.parsable_text import ParsableText


class APITasks(APIAuthenticatedPage):
    r"""
        Endpoint
          ::

            /api/v0/courses/[a-zA-Z_\-\.0-9]+/tasks(/[a-zA-Z_\-\.0-9]+)?

    """

    def _check_for_parsable_text(self, val):
        """ Util to remove parsable text from a dict, recursively """
        if isinstance(val, ParsableText):
            return val.original_content()
        if isinstance(val, list):
            for key, val2 in enumerate(val):
                val[key] = self._check_for_parsable_text(val2)
            return val
        if isinstance(val, dict):
            for key, val2 in val.items():
                val[key] = self._check_for_parsable_text(val2)
        return val

    def API_GET(self, courseid, taskid):  # pylint: disable=arguments-differ
        """
            List tasks available to the connected client. Returns a dict in the form

            ::

                {
                    "taskid1":
                    {
                        "name": "Name of the course",     #the name of the course
                        "authors": [],
                        "contact_url": "",
                        "deadline": "",
                        "status": "success"               # can be "succeeded", "failed" or "notattempted"
                        "grade": 0.0,
                        "context": ""                     # context of the task, in RST
                        "problems":                       # dict of the subproblems
                        {
                                                          # see the format of task.yaml for the content of the dict. Contains everything but
                                                          # responses of multiple-choice and match problems.
                        }
                    }
                    #...
                }

            If you use the endpoint /api/v0/courses/the_course_id/tasks/the_task_id, this dict will contain one entry or the page will return 404 Not
            Found.
        """

        try:
            course = self.course_factory.get_course(courseid)
        except:
            raise APINotFound("Course not found")

        if not self.user_manager.course_is_open_to_user(course, lti=False):
            raise APIForbidden("You are not registered to this course")

        if taskid is None:
            tasks = course.get_tasks()
        else:
            try:
                tasks = {taskid: course.get_task(taskid)}
            except:
                raise APINotFound("Task not found")

        output = []
        for taskid, task in tasks.items():
            task_cache = self.user_manager.get_task_cache(self.user_manager.session_username(), course.get_id(), task.get_id())

            data = {
                "id": taskid,
                "name": task.get_name(self.user_manager.session_language()),
                "authors": task.get_authors(self.user_manager.session_language()),
                "contact_url": task.get_contact_url(self.user_manager.session_language()),
                "status": "notviewed" if task_cache is None else "notattempted" if task_cache["tried"] == 0 else "succeeded" if task_cache["succeeded"] else "failed",
                "grade": task_cache.get("grade", 0.0) if task_cache is not None else 0.0,
                "context": task.get_context(self.user_manager.session_language()).original_content(),
                "problems": []
            }

            for problem in task.get_problems():
                pcontent = problem.get_original_content()
                pcontent["id"] = problem.get_id()
                if pcontent["type"] == "match":
                    del pcontent["answer"]
                if pcontent["type"] == "multiple_choice":
                    pcontent["choices"] = {key: val["text"] for key, val in enumerate(pcontent["choices"])}
                pcontent = self._check_for_parsable_text(pcontent)
                data["problems"].append(pcontent)

            output.append(data)

        return 200, output
