# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.
import json
import logging
import gettext

from inginious.agent import Agent, CannotCreateJobException
from inginious import get_root_path
from inginious.common.messages import BackendNewJob, BackendKillJob
from inginious.common.tasks_problems import get_problem_types
import os.path
import builtins


class MCQAgent(Agent):
    def __init__(self, context, backend_addr, friendly_name, concurrency, tasks_filesystem):
        """
        :param context: ZeroMQ context for this process
        :param backend_addr: address of the backend (for example, "tcp://127.0.0.1:2222")
        :param friendly_name: a string containing a friendly name to identify agent
        :param tasks_filesystem: FileSystemProvider to the course/tasks
        :param problem_types: Problem types dictionary
        """
        super().__init__(context, backend_addr, friendly_name, concurrency, tasks_filesystem)
        self._logger = logging.getLogger("inginious.agent.mcq")

        # Init gettext
        self._translations = {"en": gettext.NullTranslations()}
        available_translations = [x for x in os.listdir(get_root_path() + '/agent/mcq_agent/i18n') if os.path.isdir(os.path.join(get_root_path() + '/agent/mcq_agent/i18n', x))]
        self._translations.update({
            lang: gettext.translation('messages', get_root_path() + '/agent/mcq_agent/i18n', [lang]) for lang in available_translations
        })

    @property
    def environments(self):
        return {"mcq": {"mcq": {"id": "mcq", "created": 0}}}

    def check_answer(self, problems, task_input, language):
        """ Verify the answers in task_input. Returns six values:

        1. True the input is **currently** valid. (may become invalid after running the code), False else
        2. True if the input needs to be run in the VM, False else
        3. Main message, as a list (that can be join with ``\\n`` or ``<br/>`` for example)
        4. Problem specific message, as a dictionnary (tuple of result/text)
        5. Number of subproblems that (already) contain errors. <= Number of subproblems
        6. Number of errors in MCQ problems. Not linked to the number of subproblems

        """
        valid = True
        need_launch = False
        main_message = []
        problem_messages = {}
        error_count = 0
        multiple_choice_error_count = 0
        states = {}
        for problem in problems:
            problem_is_valid, problem_main_message, problem_s_messages, problem_mc_error_count, state = problem.check_answer(task_input, language)
            states[problem.get_id()] = state
            if problem_is_valid is None:
                need_launch = True
            elif problem_is_valid == False:
                error_count += 1
                valid = False
            if problem_main_message is not None:
                main_message.append(problem_main_message)
            if problem_s_messages is not None:
                problem_messages[problem.get_id()] = (("success" if problem_is_valid else "failed"), problem_s_messages)
            multiple_choice_error_count += problem_mc_error_count
        return valid, need_launch, main_message, problem_messages, error_count, multiple_choice_error_count, json.dumps(states)

    async def new_job(self, msg: BackendNewJob):
        language = msg.inputdata.get("@lang", "")
        previous_state = msg.inputdata.get("@state", "")
        translation = self._translations.get(language, gettext.NullTranslations())
        # TODO: this would probably require a refactor.
        # This may pose problem with apps that start multiple MCQAgents in the same process...
        builtins.__dict__['_'] = translation.gettext

        course_fs = self._fs.from_subfolder(msg.course_id)
        task_fs = course_fs.from_subfolder(msg.task_id)
        translations_fs = task_fs.from_subfolder("$i18n")
        if not translations_fs.exists():
            translations_fs = task_fs.from_subfolder("student").from_subfolder("$i18n")
        if not translations_fs.exists():
            translations_fs = course_fs.from_subfolder("$common").from_subfolder("$i18n")
        if not translations_fs.exists():
            translations_fs = course_fs.from_subfolder("$common").from_subfolder("student")\
                .from_subfolder("$i18n")

        if translations_fs.exists() and translations_fs.exists(language + ".mo"):
            translations = {language: gettext.GNUTranslations(translations_fs.get_fd(language + ".mo"))}
        else:
            translations = {language: gettext.NullTranslations()}

        task_problems= msg.task_problems
        problems = []
        for problemid, problem_content in task_problems.items():
            problem_class = get_problem_types().get(problem_content.get('type', ""))
            problems.append(problem_class(problemid, problem_content, translations, task_fs))

        result, need_emul, text, problems, error_count, mcq_error_count, state = self.check_answer(problems, msg.inputdata, language)

        internal_messages = {
            "_wrong_answer_multiple": _("Wrong answer. Make sure to select all the valid possibilities"),
            "_wrong_answer": _("Wrong answer"),
            "_correct_answer": _("Correct answer"),
        }

        for key, (p_result, messages) in problems.items():
            messages = [internal_messages[message] if message in internal_messages else message for message in messages]
            problems[key] = (p_result, "\n\n".join(messages))

        if need_emul:
            self._logger.warning("Task %s/%s is not a pure MCQ but has env=MCQ", msg.course_id, msg.task_id)
            raise CannotCreateJobException("Task wrongly configured as a MCQ")

        if error_count != 0:
            text.append(_("You have {} wrong answer(s).").format(error_count))
        if mcq_error_count != 0:
            text.append("\n\n" + _("Among them, you have {} invalid answers in the multiple choice questions").format(mcq_error_count))

        nb_subproblems = len(task_problems)
        if nb_subproblems == 0:
            grade = 0.0
            text.append("No subproblems defined")
            await self.send_job_result(msg.job_id, "crashed", "\n".join(text), grade, problems, {}, {}, previous_state, None)
        else:
            grade = 100.0 * float(nb_subproblems - error_count) / float(nb_subproblems)
            await self.send_job_result(msg.job_id, ("success" if result else "failed"), "\n".join(text), grade, problems, {}, {}, state, None)

    async def kill_job(self, message: BackendKillJob):
        pass
