#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.
#

""" Starts an agent """

import argparse
import logging
import os
import multiprocessing

import sys
from zmq.asyncio import ZMQEventLoop, Context
import asyncio

from inginious.common.entrypoints import get_args_and_filesystem
from inginious.agent.docker_agent import DockerAgent, DockerRuntime


def check_range(value):
    value = value.split("-")
    if len(value) != 2:
        raise argparse.ArgumentTypeError("Port range should be in the form 'begin-end', for example 1000-2000")

    try:
        begin = int(value[0])
        end = int(value[1])
    except:
        raise argparse.ArgumentTypeError("Port range should be in the form 'begin-end', for example 1000-2000")

    if begin > end:
        (begin, end) = end, begin

    return range(begin, end+1)


def check_negative(value):
    try:
        ivalue = int(value)
    except:
        raise argparse.ArgumentTypeError("%s is an invalid positive int value" % value)

    if ivalue <= 0:
        raise argparse.ArgumentTypeError("%s is an invalid positive int value" % value)
    return ivalue


class RuntimeParser(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        items = getattr(namespace, self.dest, None)
        if items is None:
            items = []
        if len(values) < 2:
            raise argparse.ArgumentError(self, "Not enough arguments")
        runtime = values[0]
        envtype = values[1]
        root = False
        shared_kernel = False
        flags = set(values[2:])
        if "root" in flags:
            flags.remove("root")
            root = True
        if "shared" in flags:
            flags.remove("shared")
            shared_kernel = True
        if shared_kernel:  # If shared_kernel, run_as_root is forbidden
            root = False
        for f in flags:
            raise argparse.ArgumentError(self, "Unknown flag {}".format(f))
        items.append(DockerRuntime(runtime=runtime, envtype=envtype, run_as_root=root, shared_kernel=shared_kernel))
        setattr(namespace, self.dest, items)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("backend", help="Address to the backend, in the form protocol://host:port. For example, tcp://127.0.0.1:2000", type=str)
    parser.add_argument("--friendly-name", help="Friendly name to help identify agent.", default="", type=str)
    parser.add_argument("--debug-host", help="Host used for job remote debugging. Should be an IP or an hostname. If not filled in, "
                                             "it will be automatically guessed", default=None, type=str)
    parser.add_argument("--debug-ports", help="Range of port for job remote debugging. By default it is 64120-64130", type=check_range, default="64120-64130")
    parser.add_argument("--tmpdir", help="Path to a directory where the agent can store information, such as caches. Defaults to ./agent_data",
                        default="./agent_data")
    parser.add_argument("--concurrency", help="Maximal number of jobs that can run concurrently on this agent. By default, it is the two times the "
                                              "number of cores available.", default=multiprocessing.cpu_count(), type=check_negative)
    parser.add_argument("-v", "--verbose", help="increase output verbosity",
                        action="store_true")
    parser.add_argument("--debugmode", help="Enables debug mode. For developers only.", action="store_true")
    parser.add_argument("--disable-autorestart", help="Disables the auto restart on agent failure.", action="store_true")
    parser.add_argument("--ssh", help="Allow this agent to handle tasks with ssh features", action="store_true",
                        default=False)
    parser.add_argument("--runtime", nargs='+', action=RuntimeParser,
                        help="Add a runtime. Expects at least 2 arguments: the name of the runtime (eg runc), "
                             "the name of the environment type (eg docker or kata). You can then add flags:\n"
                             "- 'root' indicates that the runtime starts containers as root\n"
                             "- 'shared' indicates that the containers on this runtime use the host kernel (i.e. they are not VMs)"
                             "\n"
                             "Common values are 'runc docker shared' and 'kata-runtime kata root'.")
    (args, fsprovider) = get_args_and_filesystem(parser)

    if not os.path.exists(args.tmpdir):
        os.makedirs(args.tmpdir)

    # create logger
    logger = logging.getLogger("inginious")
    logger.setLevel(logging.INFO if not args.verbose else logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO if not args.verbose else logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    closing = False
    while not closing:
        # start asyncio and zmq
        loop = ZMQEventLoop()
        asyncio.set_event_loop(loop)
        if args.debugmode:
            loop.set_debug(True)
        context = Context()

        # Create agent
        agent = DockerAgent(context, args.backend, args.friendly_name, args.concurrency, fsprovider,
                            address_host=args.debug_host, external_ports=args.debug_ports, tmp_dir=args.tmpdir,
                            runtimes=args.runtime, ssh_allowed=args.ssh)

        # Run!
        try:
            loop.run_until_complete(agent.run())
        except KeyboardInterrupt:
            closing = True
            pass # do not restart in this case
        except:
            # log the error, and restart if needed
            closing = args.disable_autorestart
            if closing:
                logger.exception("Agent has received an exception forcing it to end")
            else:
                logger.exception("Agent has received an exception forcing it to restart")
        finally:
            logger.info("Closing loop")
            loop.close()
            logger.info("Waiting for ZMQ to send remaining messages to backend (can take 1 sec)")
            context.destroy(1000)  # give zeromq 1 sec to send remaining messages
            logger.info("Done")


if __name__ == "__main__":
    main()
