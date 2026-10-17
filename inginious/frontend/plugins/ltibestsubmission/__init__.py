from bson import ObjectId, json_util
from flask import session
from werkzeug.exceptions import NotFound

from frontend.models import LISLaunch, LaunchData
from inginious.frontend.task_problems import DisplayableMultipleChoiceProblem, DisplayableCodeProblem, DisplayableMatchProblem, DisplayableFileProblem
from inginious.frontend.pages.utils import INGIniousAuthPage
from inginious.frontend.courses import Course
from inginious.frontend.models import UserTask, Submission


class LTI11BestSubmissionPage(INGIniousAuthPage):
    _lti_version = "1.1"
    _lti_model = LISLaunch

    def GET_AUTH(self, launch_id):
        # the launch must belong to the current INGInious session
        if not (launch := self._lti_model.objects(session_id=session.id, launch_id=launch_id, lti__valid=True).first()):
            raise NotFound()

        courseid, taskid = launch.lti.task
        inginious_username = session.username

        # get best submission from database
        user_best_sub = UserTask.objects(username=inginious_username, courseid=courseid, taskid=taskid).only("submissionid").get()

        if not user_best_sub:
            # no submission to retrieve
            return json_util.dumps({"status": "success", "submission": None})

        user_best_sub_id = user_best_sub.submissionid

        if user_best_sub_id is None:
            # no best submission
            return json_util.dumps({"status": "success", "submission": None})

        best_sub = Submission.objects.get(id=user_best_sub_id)

        # attach the input to the submission
        best_sub = self.submission_manager.get_input_from_submission(best_sub)

        task = Course.get(courseid).get_task(taskid)
        question_answer_list = []
        for problem in task.get_problems():
            answer = best_sub["input"][problem.get_id()]
            if isinstance(problem, DisplayableMultipleChoiceProblem):
                answer_dict = problem.get_choice_with_index(int(answer))
                has_succeeded = answer_dict['valid']
                answer = problem.gettext(session.language, answer_dict['text'])
                p_type = "mcq"
            else:
                has_succeeded = best_sub.get('result', '') == "success"
                if isinstance(problem, DisplayableMatchProblem):
                    p_type = "match"
                elif isinstance(problem, DisplayableCodeProblem):
                    p_type = "code"
                else:
                    continue
            question_answer_list.append({"question": problem.gettext(session.language,
                                                                     problem._header),
                                         "answer": answer, "success": has_succeeded,
                                         "type": p_type})

        context = task.get_context(session.language).original_content()
        return json_util.dumps({"status": "success", "submission": best_sub, "question_answer": question_answer_list,
                                "task_context": context})

    def POST_AUTH(self, launch_id):
        raise NotFound()


class LTI13BestSubmissionPage(LTI11BestSubmissionPage):
    _lti_version = "1.3"
    _lti_model = LaunchData


def init(plugin_manager, *args, **kwargs):
    """ Init the plugin """
    plugin_manager.add_page("/lti/bestsubmission/<launch_id>", LTI11BestSubmissionPage.as_view('lti11bestsubmissionpage'))
    plugin_manager.add_page("/lti1.3/bestsubmission/<launch_id>", LTI13BestSubmissionPage.as_view('lti13bestsubmissionpage'))
