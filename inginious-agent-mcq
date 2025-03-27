#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.
#

""" Starts an agent """

import argparse
import logging

from zmq.asyncio import ZMQEventLoop, Context
import asyncio

from inginious.common.entrypoints import get_args_and_filesystem
from inginious.agent.mcq_agent import MCQAgent
from inginious.common.tasks_problems import MultipleChoiceProblem, MatchProblem


def import_class(name):
    m = name.split('.')
    mod = __import__(m[0])

    for comp in m[1:]:
        mod = getattr(mod, comp)
    return mod


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("backend", help="Address to the backend, in the form protocol://host:port. For example, tcp://127.0.0.1:2000", type=str)
    parser.add_argument("--friendly-name", help="Friendly name to help identify agent.", default="", type=str)

    parser.add_argument("-v", "--verbose", help="increase output verbosity",
                        action="store_true")
    parser.add_argument("--debugmode", help="Enables debug mode. For developers only.", action="store_true")
    parser.add_argument("--disable-autorestart", help="Disables the auto restart on agent failure.",
                        action="store_true")
    parser.add_argument("--ptype", nargs="+", help="Python class import path for additionnal subproblem types")

    (args, fsprovider) = get_args_and_filesystem(parser)

    # create logger
    logger = logging.getLogger("inginious")
    logger.setLevel(logging.INFO if not args.verbose else logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO if not args.verbose else logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # load ptypes
    ptypes = {MultipleChoiceProblem, MatchProblem}
    if args.ptype:
        for ptype_loc in args.ptype:
            try:
                ptypes.add(import_class(ptype_loc))
            except:
                logger.exception("Cannot load %s, exiting", ptype_loc)
                exit(1)

    closing = False
    while not closing:
        # start asyncio and zmq
        loop = ZMQEventLoop()
        asyncio.set_event_loop(loop)
        if args.debugmode:
            loop.set_debug(True)
        context = Context()

        # Create agent
        agent = MCQAgent(context, args.backend, args.friendly_name, 1, fsprovider, {problem_type.get_type(): problem_type for problem_type in ptypes})

        # Run!
        try:
            loop.run_until_complete(agent.run())
        except KeyboardInterrupt:
            pass  # do not restart in this case
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
