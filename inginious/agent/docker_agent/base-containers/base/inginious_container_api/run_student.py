# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.
import array
import os
import signal
import socket
import tempfile
import asyncio
import msgpack
import zmq
import struct
import threading
import zmq.asyncio
from inginious_container_api.utils import read_block


def run_student(cmd, container=None,
        time_limit=0, hard_time_limit=0,
        memory_limit=0, share_network=False,
        working_dir=None, stdin=None, stdout=None, stderr=None,
        signal_handler_callback=None, ssh=False, start_student_as_root=False, teardown_script=""):
    """
    Run a command inside a student container

    :param cmd: command to be ran (as a string, with parameters). If ssh is set to True, this command will be run before launching the ssh server acting as a setup script.
    :param container: container to use. Must be present in the current agent. By default it is None, meaning the current container type will be used.

    :param time_limit: time limit in seconds. By default it is 0, which means that it will be the same as the current
                       container (NB: it does not count in the "host" container timeout!)
    :param hard_time_limit: hard time limit. By default it is 0, which means that it will be the same as the current
                       container (NB: it *does* count in the "host" container *hard* timeout!)
    :param memory_limit: memory limit in megabytes. By default it is 0, which means that it will be the same as the current
                       container (NB: it does not count in the "host" container memory limit!)
    :param share_network: share the network with the host container if True. Default is False.
    :param working_dir: The working directory for the distant command. By default, it is os.getcwd().
    :param stdin: File descriptor for stdin. Can be None, in which case a file descriptor is open to /dev/null.
    :param stdout: File descriptor for stdout. Can be None, in which case a file descriptor is open to /dev/null.
    :param stderr: File descriptor for stderr. Can be None, in which case a file descriptor is open to /dev/null.
    :param signal_handler_callback: If not None, `run` will call this callback with a function as single argument.
                                    this function can itself be called with a signal value that will immediately be sent
                                    to the remote process. See the run_student script command for an example, or
                                    the hack_signals function below.
    :param ssh: If set to True, it starts an ssh server for the student after the command finished.
    :param start_student_as_root: If set to True, it tries to execute the command as root (for ssh, it accepts connection as root).
                        Default is False. This is a Beta feature and should not be used yet.
    :param teardown_script:  command to be ran (as a string, with parameters) in the student container before closing it.
                            This parameter is mainly useful when ssh is set to True.
    :remark Calling run_student on a grading container running as root with Kata is not a possible feature yet.
    :return: the return value of the calling process. There are special values:
        - 251 means that run_student is not available in this container/environment
        - 252 means that the command was killed due to an out-of-memory
        - 253 means that the command timed out
        - 254 means that an error occurred while running the proxy
    """

    #  Checking runtimes
    shared_kernel = os.path.exists("/.__input/__shared_kernel")  # shared_kernal: boolean, True when this grading_container is running on a runtime with shared_kernel.
    both_same_kernel = shared_kernel and not start_student_as_root  # both_same_kernel: boolean, True when both grading_container and student_container will be running on a shared kernel runtime.
    user = "root" if start_student_as_root else "worker"  #start_student_as_root: boolean, True when we want to start a student_container and give root privilege.
    #  Basic files management
    if working_dir is None:
        working_dir = os.getcwd()
    if stdin is None:
        stdin = open(os.devnull, 'rb').fileno()
    if stdout is None:
        stdout = open(os.devnull, 'rb').fileno()
    if stderr is None:
        stderr = open(os.devnull, 'rb').fileno()

    try:

        server, socket_id, socket_path, path = create_student_socket(both_same_kernel)
        zmq_socket, student_container_id = start_student_container(container, time_limit, hard_time_limit, memory_limit, share_network, socket_id, ssh, start_student_as_root)
        connection = send_initial_command(socket_id, server, stdin, stdout, stderr, zmq_socket, student_container_id, cmd, teardown_script, working_dir, ssh, user, both_same_kernel)
        allow_to_send_signals(signal_handler_callback, connection, student_container_id, both_same_kernel)
        handle_ssh(ssh, connection, student_container_id, both_same_kernel)
        message = wait_until_finished(both_same_kernel, zmq_socket, stdin, stdout, stderr, student_container_id)
        unlink_unneeded_files(socket_path, path)
        return message["retval"]
    except:
        return 254


def run_student_simple(cmd, cmd_input=None, container=None,
        time_limit=0, hard_time_limit=0,
        memory_limit=0, share_network=False,
        working_dir=None, stdout_err_fuse=False, text="utf-8"):
    """
    A simpler version of `run`, which takes an input string and return the output of the command.
    This disallows interactive processes.

    :param cmd: cmd to be run.
    :param cmd_input: input of the command. Can be a string or a bytes object, or None.
    :param container: container to use. Must be present in the current agent. By default it is None, meaning the current
                      container type will be used.
    :param time_limit: time limit in seconds. By default it is 0, which means that it will be the same as the current
                       container (NB: it does not count in the "host" container timeout!)
    :param hard_time_limit: hard time limit. By default it is 0, which means that it will be the same as the current
                       container (NB: it *does* count in the "host" container *hard* timeout!)
    :param memory_limit: memory limit in megabytes. By default it is 0, which means that it will be the same as the current
                       container (NB: it does not count in the "host" container memory limit!)
    :param share_network: share the network with the host container if True. Default is False.
    :param working_dir: The working directory for the distant command. By default, it is os.getcwd().
    :param stdout_err_fuse: Weither to fuse stdout and stderr (i.e. make them use the same file descriptor)
    :param text: By default, run_simple assumes that stdout/stderr will be encoded in UTF-8. Putting another encoding
                 will make the streams encoded using this encoding. text=False indicates that the streams should be
                 opened in binary mode. In this case, run_simple returns streams in the form of binary, unencoded,
                 strings.
    :return: The output of the command, as a tuple of objects (stdout, stderr, retval). If stdout_err_fuse is True, the
             output is in the form (stdout, retval) is returned.
             The type of the returned strings (stdout, stderr) is dependent of the `text` arg.
    """
    stdin = None
    if cmd_input is not None:
        r, w = os.pipe()
        fdo = os.fdopen(w, 'w')
        fdo.write(cmd_input)
        fdo.close()
        stdin = r

    stdout_r, stdout_w = os.pipe()
    if stdout_err_fuse:
        stderr_r, stderr_w = stdout_r, stdout_w
    else:
        stderr_r, stderr_w = os.pipe()

    retval = run_student(cmd, container, time_limit, hard_time_limit, memory_limit,
                         share_network, working_dir, stdin, stdout_w, stderr_w)

    preprocess_out = (lambda x: x.decode(text)) if text is not False else (lambda x: x)

    os.fdopen(stdout_w, 'w').close()
    stdout = preprocess_out(os.fdopen(stdout_r, 'rb').read())
    if not stdout_err_fuse:
        os.fdopen(stderr_w, 'w').close()
        stderr = preprocess_out(os.fdopen(stderr_r, 'rb').read())
        return stdout, stderr, retval
    else:
        return stdout, retval



# HELPER FUNCTIONS

def _hack_signals(receive_signal):
    """ Catch every signal, and send it to the remote process """
    uncatchable = ['SIG_DFL', 'SIGSTOP', 'SIGKILL']
    for i in [x for x in dir(signal) if x.startswith("SIG")]:
        if i not in uncatchable:
            try:
                signum = getattr(signal, i)
                signal.signal(signum, lambda x, _: receive_signal)
            except:
                pass


async def _send_intern_message(send_socket, msg):
    """ Send a signal to the grading_container main process"""
    send_socket.send(msgpack.dumps(msg, use_bin_type=True))
    send_socket.recv()


def create_student_socket(both_dockers):
    """ Create a socket for the grading - student containers communication. Only used when both are using docker runtimes """
    # creates a placeholder for the socket
    DIR = "/sockets/"
    _, path = tempfile.mkstemp('', 'p', DIR)

    # Gets the socket id
    socket_id = os.path.split(path)[-1]
    socket_path = os.path.join(DIR, socket_id + ".sock")

    if both_dockers:
        # Start the socket
        server = socket.socket(socket.AF_UNIX)
        try:
            os.unlink(socket_path)
        except OSError:
            if os.path.exists(socket_path):
                raise
        server.bind(socket_path)
        server.listen(0)
        return server, socket_id, socket_path, path
    else:
        return None, socket_id, socket_path, path


def start_student_container(container, time_limit, hard_time_limit, memory_limit, share_network, socket_id, ssh, run_as_root):
    """ Ask the docker agent to create the student container """
    context = zmq.Context()
    zmq_socket = context.socket(zmq.REQ)
    zmq_socket.connect("ipc:///sockets/main.sock")
    zmq_socket.send(msgpack.dumps({"type": "run_student", "environment": container,
                                   "time_limit": time_limit, "hard_time_limit": hard_time_limit,
                                   "memory_limit": memory_limit, "share_network": share_network,
                                   "socket_id": socket_id, "ssh": ssh, "run_as_root": run_as_root},
                                  use_bin_type=True))
    # Check if the container was correctly started
    message = msgpack.loads(zmq_socket.recv(), use_list=False, strict_map_key=False)
    assert message["type"] == "run_student_started"
    student_container_id = message["container_id"]
    return zmq_socket, student_container_id


def send_initial_command(socket_id, server, stdin, stdout, stderr, zmq_socket, student_container_id, cmd, teardown_script, working_dir, ssh, user, both_dockers):
    """ Send the commands (aka: student code) to be run in the student container """
    if both_dockers:
        # Serve one and only one connection
        connection, addr = server.accept()

        # _run_student_intern should say hello
        datagram = connection.recv(1)
        assert datagram == b'H'

        # send the fds and the command/workdir directly to student_container
        connection.sendmsg([b'S'], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array("i", [stdin, stdout, stderr]))])
        connection.send(msgpack.dumps(
            {"type": "run_student_command", "student_container_id": student_container_id, "command": cmd,
             "teardown_script": teardown_script, "working_dir": working_dir, "ssh": ssh, "user": user}))
        return connection
    else:
        # Send the command to the student_container via the agent
        zmq_socket.send(msgpack.dumps(
            {"type": "run_student_init", "socket_id": socket_id, "student_container_id": student_container_id, "command": cmd,
             "teardown_script": teardown_script, "working_dir": working_dir,
             "ssh": ssh, "user": user}, use_bin_type=True))
        zmq_socket.recv() #ignore answer
        return None


def allow_to_send_signals(signal_handler_callback, connection, student_container_id, both_dockers):
    """ Allow to transfer signals """
    if signal_handler_callback is not None:
        if both_dockers:
            def receive_signal(signum_s):  # send signal directly to student_container
                signum_data = str(signum_s).zfill(3).encode("utf8")
                connection.send(signum_data)
        else:
            def receive_signal(signum_s):  # send signal to student_container via docker agent
                signum_data = str(signum_s).zfill(3).encode("utf8")
                msg = {"type": "student_signal", "student_container_id": student_container_id, "signal_data": signum_data}
                send_socket = zmq.asyncio.Context().socket(zmq.REQ)
                send_socket.connect("ipc:///sockets/main.sock")
                send_socket.send(msgpack.dumps(msg, use_bin_type=True))
                send_socket.recv()
        signal_handler_callback(receive_signal)


def wait_until_finished(both_dockers, zmq_socket, stdin, stdout, stderr, student_container_id):
    """ Dynamically handle stdin, stdout and stderr while waiting for final message """
    # Start a process to handle the stdin and send it to the student_container
    if not both_dockers:
        stdin_handler = threading.Thread(target=handle_stdin, args=(stdin, student_container_id), daemon=True)
        stdin_handler.start()

    # handle the student_container outputs and wait for final message
    message = None
    msg_type = None
    stdout_file = os.fdopen(stdout, 'wb', closefd=False)
    stderr_file = os.fdopen(stderr, 'wb', closefd=False)

    while msg_type != "run_student_retval":
        zmq_socket.send(msgpack.dumps({"type": "dummy_message"}, use_bin_type=True))  # ping pong socket
        message = msgpack.loads(zmq_socket.recv(), use_list=False, strict_map_key=False)
        msg_type = message["type"]

        if msg_type == "stdout":
            stdout_file.write(message["message"])
            stdout_file.flush()

        if msg_type == "stderr":
            stderr_file.write(message["message"])
            stderr_file.flush()
    return message


def handle_stdin(stdin, student_container_id):
    """ Read the specified stdin and send content to the student container"""
    my_context = zmq.Context()
    my_zmq_socket = my_context.socket(zmq.REQ)
    my_zmq_socket.connect("ipc:///sockets/main.sock")
    input_file = os.fdopen(stdin, 'rb', buffering=0)
    chunk_size = 512000
    while True:
        block = read_block(input_file, chunk_size)
        if block:
            my_zmq_socket.send(msgpack.dumps({"type": "stdin", "message": block, "student_container_id": student_container_id}, use_bin_type=True))
            my_zmq_socket.recv()


def unlink_unneeded_files(socket_path, path):
    """ Unlink unneeded files """
    try:
        os.unlink(socket_path)
        os.unlink(path)
    except:
        pass


def handle_ssh(ssh, connection, student_container_id, both_dockers):
    """ If ssh is required and both containers are on docker runtime, get the id and password (generated by the student_container) and sent them to the agent
    If the grading or the student container is on Kata, there is nothing to do, the information is directly sent to the agent from the student_container"""
    if not ssh:
        return
    if both_dockers:
        s = connection.recv(4)  # First 4 bytes are for the size
        message_length = struct.unpack('!I', bytes(s))[0]
        ssh_id = msgpack.loads(connection.recv(message_length))
        if ssh_id["type"] == "ssh_student":
            msg = {"type": "ssh_student", "ssh_user": ssh_id["ssh_user"], "ssh_key": ssh_id["password"],
                   "container_id": student_container_id}
            send_socket = zmq.asyncio.Context().socket(zmq.REQ)
            send_socket.connect("ipc:///sockets/main.sock")
            loop = asyncio.get_event_loop()
            task = loop.create_task(_send_intern_message(send_socket, msg))
            loop.run_until_complete(task)
            loop.close()
    return
