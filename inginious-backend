#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.
#

""" Starts a backend (scheduler) """

import argparse
import logging

from zmq.asyncio import ZMQEventLoop, Context
import asyncio

from inginious.backend.backend import Backend

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("agent", help="Address to which the agents will connect to the backend in the form protocol://host:port. For example, "
                                           "tcp://127.0.0.1:2001", type=str)
    parser.add_argument("client", help="Address to which the client will connect to the backend in the form protocol://host:port. For example, "
                                       "tcp://127.0.0.1:2000", type=str)
    parser.add_argument("-v", "--verbose", help="increase output verbosity",
                        action="store_true")
    parser.add_argument("--debugmode", help="Enables debug mode. For developers only.", action="store_true")
    args = parser.parse_args()

    # create logger
    logger = logging.getLogger("inginious")
    logger.setLevel(logging.INFO if not args.verbose else logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO if not args.verbose else logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # start asyncio and zmq
    loop = ZMQEventLoop()
    asyncio.set_event_loop(loop)
    if args.debugmode:
        loop.set_debug(True)
    context = Context()

    # Create backend
    backend = Backend(context, args.agent, args.client)

    # Run!
    try:
        loop.run_until_complete(backend.run())
    except:
        logger.exception("Closing due to exception")
    finally:
        logger.info("Closing loop")
        loop.close()
        logger.info("Waiting for ZMQ to send remaining messages to backend (can take 1 sec)")
        context.destroy(1000)  # give zeromq 1 sec to send remaining messages
        logger.info("Done")


if __name__ == "__main__":
    main()
