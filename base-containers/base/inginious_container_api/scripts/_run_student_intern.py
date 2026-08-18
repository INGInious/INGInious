# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

import subprocess
import threading
import asyncio
import shlex
import sys
import os

from inginious_container_api.utils import set_limits_user, setup_logger,\
    run_teardown_script, handle_signals, handle_ssh_session, receive_initial_command,\
    scripts_isolation


def main():
    # Setup the logger
    logger = setup_logger()

    # Get the command to be run
    socket_unix, fds, start_cmd = receive_initial_command()

    # Check security
    student_container_id = start_cmd["student_container_id"]
    user = start_cmd["user"]
    if user == "root":
        logger.info("Running as root is not supported yet.")
        sys.exit(251)

    # Add some elements to /etc/hosts and /etc/resolv.conf if needed
    system_files = {"hosts": ("/etc/hosts", True), "resolv.conf": ("/etc/resolv.conf", False)}
    for name, (spath, append) in system_files.items():
        if os.path.exists(os.path.join('/task/systemfiles/', name)):
            try:
                open(spath, 'ab' if append else 'wb').write(b'\n' + open(os.path.join('/task/systemfiles/', name), 'rb').read())
            except IOError:
                sys.exit(254)

    logger.info("student container started and received initial command")

    # Start the process
    os.chdir(start_cmd["working_dir"])
    set_limits = lambda: set_limits_user(user)  # To know if the command should be executed as root or worker
    if start_cmd["command"] is None or start_cmd["command"] == "":  # Avoid to run an empty command
        start_cmd["command"] = "echo 'info: student container started with no command set' "

    # Run the student code in its own subprocess and handle inputs/outputs
    p = subprocess.Popen(shlex.split(start_cmd["command"]), preexec_fn=set_limits, stdin=fds[0], stdout=fds[1],
                         stderr=fds[2])
    signal_thread = threading.Thread(target=lambda: handle_signals(p, socket_unix), daemon=True)
    signal_thread.start()
    retval = p.wait()
 
    logger.info("student container finished running the student code")

    scripts_isolation(True)  # Setup script finished, make the scripts directory isolated from student
    # Handle SSH
    if start_cmd["ssh"]:
        logger.info("student container is starting ssh session")
        retval = handle_ssh_session(student_container_id, socket_unix, user)
        logger.info("student container finished ssh session")

    # Run teardown script
    if start_cmd["teardown_script"]:
        scripts_isolation(False)  # Make the scripts directory available and execute the teardown script
        logger.info("student container is starting teardown script")
        run_teardown_script(start_cmd["teardown_script"], set_limits)
        logger.info("student container finished teardown script")
        
    sys.exit(retval)


if __name__ == "__main__":
    main()
