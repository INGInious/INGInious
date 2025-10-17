# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

from inginious.frontend.plugins import plugin_manager


class TestPluginManager(object):
    def make_exception(self):
        raise Exception()

    def test_exception(self):
        """ Hook Manager should silently ignore hooks that make exceptions"""
        plugin_manager.add_hook("test", self.make_exception)
        plugin_manager.add_hook("test", lambda: 42)
        retval = plugin_manager.call_hook("test")
        assert retval == [42]

    def test_multple(self):
        plugin_manager.add_hook("test", lambda: 43)
        plugin_manager.add_hook("test", lambda: 42)
        plugin_manager.add_hook("test", lambda: 44)
        retval = plugin_manager.call_hook("test")
        assert set(retval) == {42, 43, 44}
