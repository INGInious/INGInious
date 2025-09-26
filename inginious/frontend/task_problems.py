# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Displayable problems """

from abc import ABCMeta, abstractmethod
from random import Random
from flask import render_template

from inginious.common.tasks_problems import Problem, CodeProblem, CodeSingleLineProblem, \
    MatchProblem, MultipleChoiceProblem, FileProblem,  _inspect_problem_types


from inginious.frontend.parsable_text import ParsableText


def inspect_displayable_problem_types(name: str) -> dict:
    """ Get the mapping of DisplayableProblem types available by inspecting a given module.

        :param  name:   The name of the module to inspect.
        :return:        The mapping of problem name and problem class.
    """
    raw = _inspect_problem_types(name, DisplayableProblem)
    return {pbl_name: pbl_cls for pbl_name, pbl_cls in raw.items() if pbl_name is not None}

def get_default_displayable_problem_types() -> dict:
    """ Get the mapping of default DisplayableProblem types available by inspecting the current 
        module.

        :return:    The mapping of problem name and problem class.
    """
    return inspect_displayable_problem_types(__name__)


class DisplayableProblem(Problem, metaclass=ABCMeta):
    """Basic problem """

    @classmethod
    @abstractmethod
    def get_type_name(cls, language):
        pass

    def adapt_input_for_backend(self, input_data):
        """ Adapt the input from web.py for the inginious.backend """
        return input_data

    @abstractmethod
    def show_input(self, language, seed):
        """ get the html for this problem """
        pass

    @classmethod
    @abstractmethod
    def show_editbox(cls, key, language):
        """ get the edit box html for this problem """
        pass

    @classmethod
    @abstractmethod
    def show_editbox_templates(cls, key, language):
        return ""


class DisplayableCodeProblem(CodeProblem, DisplayableProblem):
    """ A basic class to display all BasicCodeProblem derivatives """

    def __init__(self, problemid, content, translations, taskfs):
        super(DisplayableCodeProblem, self).__init__(problemid, content, translations, taskfs)
        self._first_line = content.get("offset", 1)

    @classmethod
    def get_type_name(cls, language):
        return _("code")

    def adapt_input_for_backend(self, input_data):
        return input_data

    def show_input(self, language, seed):
        """ Show BasicCodeProblem and derivatives """
        header = ParsableText(self.gettext(language,self._header), "rst")
        return render_template("tasks/code.html", inputId=self.get_id(), header=header,
                                      lines=8, first_line=self._first_line, maxChars=0, language=self._language, optional=self._optional,
                                      default=self._default)

    @classmethod
    def show_editbox(cls, key, language):
        return render_template("course_admin/subproblems/code.html", key=key, multiline=True)

    @classmethod
    def show_editbox_templates(cls, key, language):
        return ""


class DisplayableCodeSingleLineProblem(CodeSingleLineProblem, DisplayableProblem):
    """ A displayable single code line problem """

    def __init__(self, problemid, content, translations, taskfs):
        super(DisplayableCodeSingleLineProblem, self).__init__(problemid, content, translations, taskfs)

    def adapt_input_for_backend(self, input_data):
        return input_data

    @classmethod
    def get_type_name(cls, language):
        return _("single-line code")

    def show_input(self, language, seed):
        """ Show InputBox """
        header = ParsableText(self.gettext(language, self._header), "rst")
        return render_template("tasks/single_line_code.html", inputId=self.get_id(), header=header, type="text",
                                      maxChars=0, optional=self._optional, default=self._default)

    @classmethod
    def show_editbox(cls, key, language):
        return render_template("course_admin/subproblems/code.html", key=key, multiline=False)

    @classmethod
    def show_editbox_templates(cls, key, language):
        return ""


class DisplayableFileProblem(FileProblem, DisplayableProblem):
    """ A displayable code problem """

    def __init__(self, problemid, content, translations, taskfs):
        super(DisplayableFileProblem, self).__init__(problemid, content, translations, taskfs)

    @classmethod
    def get_type_name(cls, language):
        return _("file upload")

    def adapt_input_for_backend(self, input_data):
        try:
            input_data[self.get_id()] = {"filename": input_data[self.get_id()].filename,
                                                  "value": input_data[self.get_id()].read()}
        except:
            input_data[self.get_id()] = {}
        return input_data

    @classmethod
    def show_editbox(cls, key, language):
        return render_template("course_admin/subproblems/file.html", key=key)

    def show_input(self, language, seed):
        """ Show FileBox """
        header = ParsableText(self.gettext(language, self._header), "rst")
        return render_template("tasks/file.html", inputId=self.get_id(), header=header,
                                      max_size=self._max_size, allowed_exts=self._allowed_exts)

    @classmethod
    def show_editbox_templates(cls, key, language):
        return ""


class DisplayableMultipleChoiceProblem(MultipleChoiceProblem, DisplayableProblem):
    """ A displayable multiple choice problem """

    def __init__(self, problemid, content, translations, taskfs):
        super(DisplayableMultipleChoiceProblem, self).__init__(problemid, content, translations, taskfs)

    @classmethod
    def get_type_name(cls, language):
        return _("multiple choice")

    def show_input(self, language, seed):
        """ Show multiple choice problems """
        choices = []
        limit = self._limit
        if limit == 0:
            limit = len(self._choices)  # no limit

        rand = Random("{}#{}#{}".format(self.get_id(), language, seed))

        # Ensure that the choices are random
        # we *do* need to copy the choices here
        random_order_choices = list(self._choices)
        if not self._unshuffle:
            rand.shuffle(random_order_choices)

        if self._multiple:
            # take only the valid choices in the first pass
            for entry in random_order_choices:
                if entry['valid']:
                    choices.append(entry)
                    limit = limit - 1
            # take everything else in a second pass
            for entry in random_order_choices:
                if limit == 0:
                    break
                if not entry['valid']:
                    choices.append(entry)
                    limit = limit - 1
        else:
            # need to have ONE valid entry
            for entry in random_order_choices:
                if not entry['valid'] and limit > 1:
                    choices.append(entry)
                    limit = limit - 1
            for entry in random_order_choices:
                if entry['valid'] and limit > 0:
                    choices.append(entry)
                    limit = limit - 1
        if not self._unshuffle:
            rand.shuffle(choices)
        else:
            choices = sorted(choices, key=lambda k: k['index'])
        header = ParsableText(self.gettext(language, self._header), "rst")
        return render_template("tasks/multiple_choice.html", pid=self.get_id(), header=header,
                                      checkbox=self._multiple, choices=choices,
                                      func=lambda text: ParsableText(
                                          self.gettext(language, text) if text else "", "rst"
                                      )
                               )

    @classmethod
    def show_editbox(cls, key, language):
        return render_template("course_admin/subproblems/multiple_choice.html", key=key)

    @classmethod
    def show_editbox_templates(cls, key, language):
        return render_template("course_admin/subproblems/multiple_choice_templates.html", key=key)


class DisplayableMatchProblem(MatchProblem, DisplayableProblem):
    """ A displayable match problem """

    def __init__(self, problemid, content, translations, taskfs):
        super(DisplayableMatchProblem, self).__init__(problemid, content, translations, taskfs)

    @classmethod
    def get_type_name(cls, language):
        return _("match")

    def show_input(self, language, seed):
        """ Show MatchProblem """
        header = ParsableText(self.gettext(language, self._header), "rst")
        return render_template("tasks/match.html", inputId=self.get_id(), header=header)

    @classmethod
    def show_editbox(cls, key, language):
        return render_template("course_admin/subproblems/match.html", key=key)

    @classmethod
    def show_editbox_templates(cls, key, language):
        return ""
