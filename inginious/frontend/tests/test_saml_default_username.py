# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

from types import SimpleNamespace
from unittest import mock

import flask
import mongoengine
import mongomock
import pytest
import yaml

from inginious.common.base import get_default_username
from inginious.frontend.models import User
from inginious.frontend.user_manager import AuthMethod, UserManager
from inginious.scripts import rename_saml_usernames
from inginious.scripts.rename_saml_usernames import SAML_PLUGIN, apply_rename, find_course_references, plan_renames

REGEX = r"(s\d{7})(@.*)?"
AUTH_CONFIG = {"id": "saml", "default_username": {"regex": REGEX}}


class TestGetDefaultUsername:
    @pytest.mark.parametrize("uid", ["s0261234", "s0261234@ad.ua.ac.be"])
    def test_uid(self, uid):
        assert get_default_username(AUTH_CONFIG, uid, "a.b@example.org", {}) == "s0261234"

    def test_email_and_additional_sources(self):
        email = {"default_username": {"source": "email", "regex": REGEX}}
        assert get_default_username(email, "x", "s0261234@ad.ua.ac.be", {}) == "s0261234"
        additional = {"default_username": {"source": "student", "regex": REGEX}}
        assert get_default_username(additional, "x", "y", {"student": "s0261234"}) == "s0261234"

    @pytest.mark.parametrize("uid", ["p123456", "xs0261234", "s0261234x", "", None])
    def test_no_match(self, uid):
        assert get_default_username(AUTH_CONFIG, uid, "a.b@example.org", {}) == ""

    def test_not_configured(self):
        assert get_default_username({"id": "saml"}, "s0261234", "a.b@example.org", {}) == ""
        assert get_default_username(AUTH_CONFIG, "x", "y", {}) == ""


class FakeAuthMethod(AuthMethod):
    get_id = get_auth_link = callback = get_name = get_imlink = lambda self, *args: ""

    def get_default_username(self, uid, email, additional):
        return get_default_username(AUTH_CONFIG, uid, email, additional)


class TestBindUser:
    @pytest.fixture(autouse=True)
    def environment(self):
        mongoengine.disconnect()
        mongoengine.connect("test", host="mongodb://localhost", mongo_client_class=mongomock.MongoClient)
        self.manager = UserManager.__new__(UserManager)
        self.manager._logger = mock.MagicMock()
        self.manager._auth_methods = {"saml": FakeAuthMethod()}
        session = SimpleNamespace(loggedin=False, language="en")
        with flask.Flask(__name__).test_request_context(), \
                mock.patch("inginious.frontend.user_manager.session", session):
            yield
        mongoengine.disconnect()

    def bind(self, uid, email):
        return self.manager.bind_user("saml", (uid, "Real Name", email, {}))

    def test_new_student_gets_identifier(self):
        assert self.bind("s0261234@ad.ua.ac.be", "a.b@example.org")
        assert User.objects.get(email="a.b@example.org").username == "s0261234"

    def test_new_user_without_identifier_chooses(self):
        assert self.bind("p123456", "staff@example.org")
        assert User.objects.get(email="staff@example.org").username == ""

    def test_taken_username_is_not_reused(self):
        User(username="s0261234", realname="Other", email="other@example.org").save()
        assert self.bind("s0261234", "a.b@example.org")
        assert User.objects.get(email="a.b@example.org").username == ""

    def test_existing_account_keeps_username(self):
        User(username="chosen", realname="A", email="a.b@example.org",
             bindings={"saml": ["s0261234", {}]}).save()
        assert self.bind("s0261234", "a.b@example.org")
        assert User.objects.get(email="a.b@example.org").username == "chosen"


class TestRename:
    @pytest.fixture
    def database(self):
        return mongomock.MongoClient().test

    @staticmethod
    def add_user(database, username, uid, email=None):
        email = email or uid + "@example.org"
        database.users.insert_one({"username": username, "email": email, "bindings": {"saml": [uid, {}]}})

    def plan(self, database, superadmins=()):
        return plan_renames(database, [AUTH_CONFIG], superadmins)

    def test_plan(self, database):
        self.add_user(database, "chosen", "s0000001")
        self.add_user(database, "", "s0000002")
        self.add_user(database, "s0000003", "s0000003")
        self.add_user(database, "staff", "p123456")
        self.add_user(database, "root", "s0000004")
        self.add_user(database, "dup1", "s0000005", "d1@example.org")
        self.add_user(database, "dup2", "s0000005", "d2@example.org")
        self.add_user(database, "taker", "s0000006")
        database.users.insert_one({"username": "s0000006", "email": "local@example.org", "bindings": {}})

        renames, skipped = self.plan(database, ["root"])
        assert {u["username"]: u["new_username"] for u in renames} == {"chosen": "s0000001", "": "s0000002"}
        assert {u["username"] for u, _ in skipped} == {"staff", "root", "dup1", "dup2", "taker"}

    def test_apply_renames_all_references(self, database):
        self.add_user(database, "chosen", "s0000001")
        database.submissions.insert_one({"username": ["other", "chosen"]})
        database.user_tasks.insert_one({"username": "chosen"})
        database.courses.insert_one({"students": ["chosen", "other"]})
        database.audiences.insert_one({"students": ["chosen"], "tutors": ["chosen"]})
        database.groups.insert_one({"students": ["chosen"]})
        database.lis_outcome_queue.insert_one({"username": "chosen"})
        database.lti_grade_queue.insert_one({"username": "chosen"})
        database.sessions.insert_one({"email": "s0000001@example.org", "username": "chosen"})

        apply_rename(database, self.plan(database)[0][0])

        assert database.users.find_one({})["username"] == "s0000001"
        assert database.submissions.find_one({})["username"] == ["other", "s0000001"]
        assert database.user_tasks.find_one({})["username"] == "s0000001"
        assert database.courses.find_one({})["students"] == ["s0000001", "other"]
        audience = database.audiences.find_one({})
        assert (audience["students"], audience["tutors"]) == (["s0000001"], ["s0000001"])
        assert database.groups.find_one({})["students"] == ["s0000001"]
        assert database.lis_outcome_queue.find_one({})["username"] == "s0000001"
        assert database.lti_grade_queue.find_one({})["username"] == "s0000001"
        assert database.sessions.find_one({})["username"] == "s0000001"

    def test_empty_username_does_not_touch_others(self, database):
        self.add_user(database, "", "s0000002")
        database.user_tasks.insert_one({"username": ""})
        database.sessions.insert_one({"email": "s0000002@example.org", "username": ""})
        database.sessions.insert_one({"email": "other@example.org", "username": ""})

        apply_rename(database, self.plan(database)[0][0])

        assert database.user_tasks.find_one({})["username"] == ""
        assert database.sessions.find_one({"email": "s0000002@example.org"})["username"] == "s0000002"
        assert database.sessions.find_one({"email": "other@example.org"})["username"] == ""

    def test_second_run_is_a_no_op(self, database):
        self.add_user(database, "chosen", "s0000001")
        apply_rename(database, self.plan(database)[0][0])
        assert self.plan(database) == ([], [])

    def test_course_references(self, tmp_path):
        (tmp_path / "c").mkdir()
        (tmp_path / "c" / "course.yaml").write_text("admins:\n- chosen\ntutors: []\nregistration_ac_list:\n- other\n")
        path = str(tmp_path / "c" / "course.yaml")
        assert find_course_references(str(tmp_path), {"chosen"}) == [(path, "admins", "chosen")]

    def test_duplicate_list_entries(self, database):
        self.add_user(database, "chosen", "s0000001")
        database.courses.insert_one({"students": ["chosen", "other", "chosen"]})
        apply_rename(database, self.plan(database)[0][0])
        assert database.courses.find_one({})["students"] == ["s0000001", "other", "s0000001"]

    @pytest.fixture
    def run_main(self, database, tmp_path, monkeypatch, capsys):
        (tmp_path / "tasks" / "c").mkdir(parents=True)
        (tmp_path / "tasks" / "c" / "course.yaml").write_text("tutors:\n- chosen\n")
        config = tmp_path / "configuration.yaml"
        config.write_text(yaml.safe_dump({
            "tasks_directory": str(tmp_path / "tasks"),
            "superadmins": ["root"],
            "plugins": [{"plugin_module": SAML_PLUGIN, **AUTH_CONFIG}, {"plugin_module": "other", "id": "saml"}]
        }))
        monkeypatch.setattr(rename_saml_usernames, "MongoClient", lambda host: {"INGInious": database})

        def run(*args):
            monkeypatch.setattr("sys.argv", ["rename_saml_usernames", "-c", str(config), *args])
            rename_saml_usernames.main()
            return capsys.readouterr().out
        return run

    def test_main_only_displays_without_apply(self, database, run_main):
        self.add_user(database, "chosen", "s0000001")
        database.user_tasks.insert_one({"username": "chosen"})

        output = run_main()

        assert "RENAME 'chosen' -> 's0000001'" in output
        assert "UPDATE MANUALLY" in output and "'chosen' in tutors" in output
        assert database.users.find_one({})["username"] == "chosen"
        assert database.user_tasks.find_one({})["username"] == "chosen"

    def test_main_apply(self, database, run_main):
        self.add_user(database, "chosen", "s0000001")
        database.user_tasks.insert_one({"username": "chosen"})

        assert "Renamed 1 accounts" in run_main("--apply")

        assert database.users.find_one({})["username"] == "s0000001"
        assert database.user_tasks.find_one({})["username"] == "s0000001"
        assert "Would rename 0 accounts" in run_main()
