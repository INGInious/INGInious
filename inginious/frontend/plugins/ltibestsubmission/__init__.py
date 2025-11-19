from bson import ObjectId, json_util

from werkzeug.exceptions import NotFound
from inginious.frontend.task_problems import DisplayableMultipleChoiceProblem, DisplayableCodeProblem, DisplayableMatchProblem, DisplayableFileProblem
from inginious.frontend.pages.utils import INGIniousAuthPage
from inginious.frontend.courses import Course


class LTI11BestSubmissionPage(INGIniousAuthPage):
    _field = "consumer_key"

    def is_lti_page(self):
        return True

    def GET_AUTH(self):
        data = self.user_manager.session_lti_info()
        if data is None:
            raise NotFound()

        courseid, taskid = data["task"]

        # get the INGInious username from the ToolConsumer-provided username
        inginious_usernames = list(self.database.users.find(
            {"ltibindings." + courseid + "." + data[self._field]: data["username"]}
        ))

        if not inginious_usernames:
            return json_util.dumps({"status": "error", "message": "user not bound with lti"})

        inginious_username = inginious_usernames[0]["username"]

        # get best submission from database
        user_best_sub = list(self.database.user_tasks.find(
            {"username": inginious_username, "courseid": courseid, "taskid": taskid},
            {"submissionid": 1, "_id": 0}))

        if not user_best_sub:
            # no submission to retrieve
            return json_util.dumps({"status": "success", "submission": None})

        user_best_sub_id = user_best_sub[0]["submissionid"]

        if user_best_sub_id is None:
            # no best submission
            return json_util.dumps({"status": "success", "submission": None})

        best_sub = list(self.database.submissions.find({"_id": ObjectId(user_best_sub_id)}))[0]

        # attach the input to the submission
        best_sub = self.submission_manager.get_input_from_submission(best_sub)

        task = Course.get(courseid, self.fs_provider).get_task(taskid)
        question_answer_list = []
        for problem in task.get_problems():
            answer = best_sub["input"][problem.get_id()]
            if isinstance(problem, DisplayableMultipleChoiceProblem):
                answer_dict = problem.get_choice_with_index(int(answer))
                has_succeeded = answer_dict['valid']
                answer = problem.gettext(self.user_manager.session_language(), answer_dict['text'])
                p_type = "mcq"
            else:
                has_succeeded = best_sub.get('result', '') == "success"
                if isinstance(problem, DisplayableMatchProblem):
                    p_type = "match"
                elif isinstance(problem, DisplayableCodeProblem):
                    p_type = "code"
                else:
                    continue
            question_answer_list.append({"question": problem.gettext(self.user_manager.session_language(),
                                                                     problem._header),
                                         "answer": answer, "success": has_succeeded,
                                         "type": p_type})

        context = task.get_context(self.user_manager.session_language()).original_content()
        return json_util.dumps({"status": "success", "submission": best_sub, "question_answer": question_answer_list,
                                "task_context": context})

    def POST_AUTH(self):
        raise NotFound()


class LTI13BestSubmissionPage(LTI11BestSubmissionPage):
    _field = "platform_instance_id"


def init(plugin_manager, *args, **kwargs):
    """ Init the plugin """
    plugin_manager.add_page("/lti/bestsubmission", LTI11BestSubmissionPage.as_view('lti11bestsubmissionpage'))
    plugin_manager.add_page("/lti1.3/bestsubmission", LTI11BestSubmissionPage.as_view('lti13bestsubmissionpage'))
