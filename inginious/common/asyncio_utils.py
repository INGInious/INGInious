# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

"""
    Utilities for asyncio
"""

import asyncio
import threading
import weakref
from functools import wraps, partial
from typing import TypeVar, Generic


class AsyncIteratorWrapper(object):
    """ A wrapper that converts old-style-generators to async generators using run_in_executor """
    def __init__(self, obj):
        self._it = obj
        self._loop = asyncio.get_event_loop()
        self._queue = asyncio.Queue()
        self._last_item = object()
        self._thread = threading.Thread(target=self._unroll)
        self._thread.daemon = True
        self._thread.start()

    def __aiter__(self):
        return self

    async def __anext__(self):
        value = await self._queue.get()
        if value == self._last_item:
            raise StopAsyncIteration
        return value

    async def _add_to_queue(self, o):
        await self._queue.put(o)

    def _unroll(self):
        try:
            for i in self._it:
                self._loop.call_soon_threadsafe(asyncio.ensure_future, self._add_to_queue(i))
        except Exception:
            pass
        self._loop.call_soon_threadsafe(asyncio.ensure_future, self._add_to_queue(self._last_item))


T = TypeVar('T')


class AsyncProxy(Generic[T]):
    """ An asyncio proxy for modules and classes """
    def __init__(self, module: T, loop=None, executor=None):
        self._module = module
        self._loop = loop or asyncio.get_event_loop()
        self._executor = executor

    @property
    def sync(self) -> T:
        """ Return the original sync module/class """
        return self._module

    def __getattr__(self, name):
        function = getattr(self._module, name)
        if not callable(function):
            return AsyncProxy(function)

        @wraps(function)
        async def _inner(*args, **kwargs):
            f = partial(function, *args, **kwargs)
            return await self._loop.run_in_executor(self._executor, f)

        return _inner


# Mapping from asyncio loops -> sets of running tasks, used in create_safe_task
# This is a weakref dict: if a loop is not referenced anywhere else, it will be garbage collected and
# removed from this dict.
__background_tasks = weakref.WeakKeyDictionary()


def create_safe_task(loop, logger, coroutine):
    """ Calls loop.create_task with a safe (with logged exception / protection against garbage collection) coroutine """
    task = loop.create_task(coroutine)
    task.add_done_callback(lambda task: __log_safe_task(logger, task))
    if loop not in __background_tasks:
        __background_tasks[loop] = set()
    __background_tasks[loop].add(task)
    task.add_done_callback(__background_tasks[loop].discard)
    return task


def __log_safe_task(logger, task):
    """ Logs the exception if one occurs in a given task """
    exception = task.exception()
    if exception is not None:
        logger.exception("An exception occurred while running a Task", exc_info=exception)