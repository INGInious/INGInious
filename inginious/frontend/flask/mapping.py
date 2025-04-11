# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

from werkzeug.routing import BaseConverter

from inginious.frontend.pages.admin.admin import AdministrationUsersPage, \
    AdministrationUserActionPage
from inginious.frontend.pages.maintenance import MaintenancePage
from inginious.frontend.pages.utils import INGIniousStaticPage
from inginious.frontend.pages.index import IndexPage
from inginious.frontend.pages.queue import QueuePage
from inginious.frontend.pages.courselist import CourseListPage
from inginious.frontend.pages.mycourses import MyCoursesPage
from inginious.frontend.pages.preferences.bindings import BindingsPage
from inginious.frontend.pages.preferences.delete import DeletePage
from inginious.frontend.pages.preferences.profile import ProfilePage
from inginious.frontend.pages.preferences.utils import PrefRedirectPage
from inginious.frontend.pages.utils import SignInPage, LogOutPage
from inginious.frontend.pages.register import RegistrationPage
from inginious.frontend.pages.social import AuthenticationPage, CallbackPage
from inginious.frontend.pages.course_register import CourseRegisterPage
from inginious.frontend.pages.course import CoursePage
from inginious.frontend.pages.tasks import TaskPage, TaskPageStaticDownload
from inginious.frontend.pages.lti.v1_1 import LTI11LaunchPage, LTI11BindPage, LTI11LoginPage
from inginious.frontend.pages.lti.v1_3 import LTI13LaunchPage, LTI13BindPage, LTI13LoginPage, LTI13OIDCLoginPage, LTI13JWKSPage
from inginious.frontend.pages.lti import LTITaskPage, LTIAssetPage
from inginious.frontend.pages.group import GroupPage
from inginious.frontend.pages.marketplace import MarketplacePage
from inginious.frontend.pages.marketplace_course import MarketplaceCoursePage
from inginious.frontend.pages.api.auth_methods import APIAuthMethods
from inginious.frontend.pages.api.authentication import APIAuthentication
from inginious.frontend.pages.api.courses import APICourses
from inginious.frontend.pages.api.tasks import APITasks
from inginious.frontend.pages.api.submissions import APISubmissions
from inginious.frontend.pages.api.submissions import APISubmissionSingle
from inginious.frontend.pages.course_admin.utils import CourseRedirectPage
from inginious.frontend.pages.course_admin.settings import CourseSettingsPage
from inginious.frontend.pages.course_admin.student_list import CourseStudentListPage
from inginious.frontend.pages.course_admin.student_info import CourseStudentInfoPage
from inginious.frontend.pages.course_admin.submission import SubmissionPage
from inginious.frontend.pages.course_admin.submissions import CourseSubmissionsPage
from inginious.frontend.pages.course_admin.task_list import CourseTaskListPage
from inginious.frontend.pages.course_admin.audience_edit import CourseEditAudience
from inginious.frontend.pages.course_admin.task_edit import CourseEditTask
from inginious.frontend.pages.course_admin.task_edit_file import CourseTaskFiles
from inginious.frontend.pages.course_admin.task_edit_file import CourseTaskFileUpload
from inginious.frontend.pages.course_admin.danger_zone import CourseDangerZonePage
from inginious.frontend.pages.course_admin.statistics import CourseStatisticsPage
from inginious.frontend.pages.course_admin.search_user import CourseAdminSearchUserPage


def init_flask_maintenance_mapping(flask_app):
    flask_app.add_url_rule('/', view_func=MaintenancePage.as_view('maintenancepage.alias'))
    flask_app.add_url_rule('/<path:path>', view_func=MaintenancePage.as_view('maintenancepage'))


def init_flask_mapping(flask_app):
    flask_app.add_url_rule('/', view_func=IndexPage.as_view('indexpage'))
    flask_app.add_url_rule('/index', view_func=IndexPage.as_view('indexpage.alias'))
    flask_app.add_url_rule('/signin', view_func=SignInPage.as_view('signinpage'))
    flask_app.add_url_rule('/logout', view_func=LogOutPage.as_view('logoutpage'))
    flask_app.add_url_rule('/register', view_func=RegistrationPage.as_view('registrationpage'))
    flask_app.add_url_rule('/queue', view_func=QueuePage.as_view('queuepage'))
    flask_app.add_url_rule('/register/<courseid>',
                           view_func=CourseRegisterPage.as_view('courseregisterpage'))
    flask_app.add_url_rule('/marketplace', view_func=MarketplacePage.as_view('marketplacepage'))
    flask_app.add_url_rule('/marketplace/<courseid>',
                           view_func=MarketplaceCoursePage.as_view('marketplacetasksetpage'))
    flask_app.add_url_rule('/course/<courseid>', view_func=CoursePage.as_view('coursepage'))
    flask_app.add_url_rule('/course/<courseid>/<taskid>', view_func=TaskPage.as_view('taskpage'))
    flask_app.add_url_rule('/course/<courseid>/<taskid>/<path:path>',
                           view_func=TaskPageStaticDownload.as_view('taskpagestaticdownload'))
    flask_app.add_url_rule('/group/<courseid>', view_func=GroupPage.as_view('grouppage'))
    flask_app.add_url_rule('/auth/signin/<auth_id>',
                           view_func=AuthenticationPage.as_view('authenticationpage'))
    flask_app.add_url_rule('/auth/callback/<auth_id>',
                           view_func=CallbackPage.as_view('callbackpage'))
    flask_app.add_url_rule('/pages/<pageid>', view_func=INGIniousStaticPage.as_view('staticpage'))
    flask_app.add_url_rule('/courselist', view_func=CourseListPage.as_view('courselistpage'))
    flask_app.add_url_rule('/mycourses', view_func=MyCoursesPage.as_view('mycoursespage'))
    flask_app.add_url_rule('/preferences', view_func=PrefRedirectPage.as_view('prefredirectpage'))
    flask_app.add_url_rule('/preferences/bindings',
                           view_func=BindingsPage.as_view('bindingspage'))
    flask_app.add_url_rule('/preferences/delete', view_func=DeletePage.as_view('deletepage'))
    flask_app.add_url_rule('/preferences/profile', view_func=ProfilePage.as_view('profilepage'))
    flask_app.add_url_rule('/lti/task', view_func=LTITaskPage.as_view('ltitaskpage'))
    flask_app.add_url_rule('/lti/<courseid>/<taskid>',
                           view_func=LTI11LaunchPage.as_view('ltilaunchpage'))
    flask_app.add_url_rule('/lti/bind', view_func=LTI11BindPage.as_view('ltibindpage'))
    flask_app.add_url_rule('/lti/login', view_func=LTI11LoginPage.as_view('ltiloginpage'))
    flask_app.add_url_rule('/lti/asset/<path:asset_url>',
                           view_func=LTIAssetPage.as_view('ltiassetpage'))

    flask_app.add_url_rule('/lti1.3/oidc_login/<courseid>',
                           view_func=LTI13OIDCLoginPage.as_view('lti13oidcloginpage'))
    flask_app.add_url_rule('/lti1.3/launch/<courseid>/<taskid>',
                           view_func=LTI13LaunchPage.as_view('lti13launchpage'))
    flask_app.add_url_rule('/lti1.3/jwks/<courseid>/<keyset_hash>', view_func=LTI13JWKSPage.as_view('lti13jwkspage'))
    flask_app.add_url_rule('/lti1.3/bind', view_func=LTI13BindPage.as_view('lti13bindpage'))
    flask_app.add_url_rule('/lti1.3/login', view_func=LTI13LoginPage.as_view('lti13loginpage'))

    flask_app.add_url_rule('/admin/<courseid>',
                           view_func=CourseRedirectPage.as_view('courseredirect'))
    flask_app.add_url_rule('/admin/<courseid>/settings',
                           view_func=CourseSettingsPage.as_view('coursesettingspage'))
    flask_app.add_url_rule('/admin/<courseid>/students',
                           view_func=CourseStudentListPage.as_view('coursestudentlistpage'))
    flask_app.add_url_rule('/admin/<courseid>/student/<username>',
                           view_func=CourseStudentInfoPage.as_view('coursestudentinfopage'))
    flask_app.add_url_rule('/submission/<submissionid>',
                           view_func=SubmissionPage.as_view('submissionpage'))
    flask_app.add_url_rule('/admin/<courseid>/submissions',
                           view_func=CourseSubmissionsPage.as_view('coursesubmissionspage'))
    flask_app.add_url_rule('/admin/<courseid>/tasks',
                           view_func=CourseTaskListPage.as_view('coursetasklistpage'))
    flask_app.add_url_rule('/admin/<courseid>/edit/audience/<audienceid>',
                           view_func=CourseEditAudience.as_view('courseditaudience'))
    flask_app.add_url_rule('/admin/<courseid>/edit/task/<taskid>',
                           view_func=CourseEditTask.as_view('coursedittask'))
    flask_app.add_url_rule('/admin/<courseid>/edit/task/<taskid>/files',
                           view_func=CourseTaskFiles.as_view('coursetaskfiles'))
    flask_app.add_url_rule('/admin/<courseid>/edit/task/<taskid>/dd_upload',
                           view_func=CourseTaskFileUpload.as_view('coursetaskfileupload'))
    flask_app.add_url_rule('/admin/<courseid>/search_user/<request>',
                           view_func=CourseAdminSearchUserPage.as_view('searchuserpage'))
    flask_app.add_url_rule('/admin/<courseid>/danger',
                           view_func=CourseDangerZonePage.as_view('coursedangerzonepage'))
    flask_app.add_url_rule('/admin/<courseid>/stats',
                           view_func=CourseStatisticsPage.as_view('coursestatisticspage'))
    flask_app.add_url_rule('/api/v0/auth_methods',
                           view_func=APIAuthMethods.as_view('apiauthmethods'))
    flask_app.add_url_rule('/api/v0/authentication',
                           view_func=APIAuthentication.as_view('apiauthentication'))
    flask_app.add_url_rule('/api/v0/courses', view_func=APICourses.as_view('apicourses.alias'),
                           defaults={'courseid': None})
    flask_app.add_url_rule('/api/v0/courses/<courseid>',
                           view_func=APICourses.as_view('apicourses'))
    flask_app.add_url_rule('/api/v0/courses/<courseid>/tasks',
                           view_func=APITasks.as_view('apitasks.alias'), defaults={'taskid': None})
    flask_app.add_url_rule('/api/v0/courses/<courseid>/tasks/<taskid>',
                           view_func=APITasks.as_view('apitasks'))
    flask_app.add_url_rule('/api/v0/courses/<courseid>/tasks/<taskid>/submissions',
                           view_func=APISubmissions.as_view('apisubmissions.alias'))
    flask_app.add_url_rule('/api/v0/courses/<courseid>/tasks/<taskid>/submissions/<submissionid>',
                           view_func=APISubmissionSingle.as_view('apisubmissions'))
    flask_app.add_url_rule('/administrator/users',
                           view_func=AdministrationUsersPage.as_view('administrationuserspage'))
    flask_app.add_url_rule('/administrator/user_action',
                           view_func=AdministrationUserActionPage.as_view('administrationuseractionpage'))
