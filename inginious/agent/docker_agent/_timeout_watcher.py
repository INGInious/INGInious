# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

"""
Abstractions that provide zeromq-agents that talk with cgroups.
"""

import asyncio
import logging

from inginious.common.asyncio_utils import AsyncIteratorWrapper


class TimeoutWatcher(object):
    """Looks for container timeouts"""

    def __init__(self, docker_interface):
        """docker_interface is an ASYNC interface to docker"""

        self._logger = logging.getLogger("inginious.agent.docker")
        self._loop = asyncio.get_event_loop()
        self._container_had_error = set()
        self._watching = set()
        self._docker_interface = docker_interface
        self._running_asyncio_tasks = set()

    async def clean(self):
        """Close all the running tasks watching for a container timeout. All references to
        containers are removed: any attempt to was_killed after a call to clean() will return None.
        """
        for x in self._running_asyncio_tasks:
            x.cancel()
        self._container_had_error = set()
        self._watching = set()
        self._running_asyncio_tasks = set()

    async def was_killed(self, container_id):
        """
        This method has to be called *once, and only once* for each container registered in `register_container`.
        :param container_id: the container id to check
        :return: a string containing "timeout" if the container was killed. None if it was not (std format for container errors)
        """
        if container_id in self._watching:
            self._watching.remove(container_id)
        if container_id in self._container_had_error:
            self._container_had_error.remove(container_id)
            return "timeout"
        return None

    async def register_container(self, container_id, timeout, hard_timeout):
        self._watching.add(container_id)
        task = self._loop.create_task(
            self._handle_container_timeout(container_id, timeout)
        )
        self._running_asyncio_tasks.add(task)
        task.add_done_callback(self._remove_safe_task)

        self._loop.call_later(
            hard_timeout,
            asyncio.ensure_future,
            self._handle_container_hard_timeout(container_id, hard_timeout),
        )

    async def _handle_container_timeout(self, container_id, timeout):
        """
        Check timeout with docker stats
        :param container_id:
        :param timeout: in seconds (cpu time)
        """
        try:
            docker_stats = await self._docker_interface.get_stats(container_id)
            source = AsyncIteratorWrapper(docker_stats)
            nano_timeout = timeout * (10**9)
            async for upd in source:
                if upd is None:
                    await self._kill_it_with_fire(container_id)
                self._logger.debug("%i", upd["cpu_stats"]["cpu_usage"]["total_usage"])
                if upd["cpu_stats"]["cpu_usage"]["total_usage"] > nano_timeout:
                    self._logger.info(
                        "Killing container %s as it used %i CPU seconds (max was %i)",
                        container_id,
                        int(upd["cpu_stats"]["cpu_usage"]["total_usage"] / (10**9)),
                        timeout,
                    )
                    await self._kill_it_with_fire(container_id)
                    return
        except asyncio.CancelledError:
            pass
        except:
            self._logger.exception("Exception in _handle_container_timeout")

    async def _handle_container_hard_timeout(self, container_id, hard_timeout):
        """
        Kills a container (should be called with loop.call_later(hard_timeout, ...)) and displays a message on the log
        :param container_id:
        :param hard_timeout:
        :return:
        """
        if container_id in self._watching:
            self._logger.info(
                "Killing container %s as it used its %i wall time seconds",
                container_id,
                hard_timeout,
            )
            await self._kill_it_with_fire(container_id)

    async def _kill_it_with_fire(self, container_id):
        """
        Kill a container, with fire.
        """
        if container_id in self._watching:
            self._watching.remove(container_id)
            self._container_had_error.add(container_id)
            try:
                await self._docker_interface.kill_container(container_id)
            except:
                pass  # is ok

    def _remove_safe_task(self, task):
        """Remove a task from _running_asyncio_tasks"""
        try:
            self._running_asyncio_tasks.remove(task)
        except:
            pass
