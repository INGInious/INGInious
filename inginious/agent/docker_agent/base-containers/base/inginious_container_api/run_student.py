# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.
import os
import signal
import socket
import tempfile
import msgpack
import secrets
from inginious_container_api import ProxyToAgent
from inginious.agent.docker_agent.common import GRADING_CONTAINER_SK
from inginious.agent.docker_agent.messages import StudentRun, _MsgBase, MsgType, StudentSsh

TOKEN_LEN = 64


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
        # Student - grading channel.
        server, socket_id, socket_path, path = create_student_socket()
 
        # Channel towards grading process.
        grading_sk = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        grading_sk.connect(GRADING_CONTAINER_SK)

        # Token to authenticate student container.
        token = secrets.token_bytes(TOKEN_LEN)

        # Request the Agent to create the student container.
        msg = StudentRun(
            container,
            time_limit,
            hard_time_limit,
            memory_limit,
            token,
            socket_id,
            share_network,
            ssh,
            start_student_as_root,
        )
        grading_sk.send(ProxyToAgent(msg).serialize())

        # Check Agent status.
        resp = _MsgBase.deserialize(grading_sk.recv(1000))
        assert resp.type == MsgType.StudentStarted
        student_container_id = msg.container_id

        connection = send_initial_command(socket_id, server, stdin, stdout, stderr, student_container_id, cmd, teardown_script, working_dir, ssh, user, token)
        allow_to_send_signals(signal_handler_callback, connection, student_container_id)
        if ssh:
            handle_ssh(connection, student_container_id)
        message = wait_until_finished(zmq_socket, stdin, stdout, stderr, student_container_id)

        unlink_unneeded_files([socket_path, path])
        # return message["retval"]
        return 0
    except Exception as e:
        print(e)
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
            except Exception:
                pass


def create_student_socket():
    """ Create a socket for the grading - student containers communication. Only used when both are using docker runtimes """
    # creates a placeholder for the socket
    DIR = "/dev/shm/"
    _, path = tempfile.mkstemp('', 'p', DIR)

    # Gets the socket id
    socket_id = os.path.split(path)[-1]
    socket_path = os.path.join(DIR, socket_id + ".sock")

    # Start the socket
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        os.unlink(socket_path)
    except OSError:
        if os.path.exists(socket_path):
            raise
    server.bind(socket_path)
    server.listen(0)
    return server, socket_id, socket_path, path
    
def send_initial_command(socket_id, server, stdin, stdout, stderr, student_container_id, cmd, teardown_script, working_dir, ssh, user, token):
    """ Send the commands (aka: student code) to be run in the student container """

    # TODO: For running another kernel, see https://github.com/INGInious/INGInious/pull/949.
    # Virtme container will handle msg proxying.
    
    while True:
        # _run_student_intern should send back our token.
        # We try to accept connections until we get the current token.
        connection, addr = server.accept()
        rx_token = connection.recv(TOKEN_LEN)
        if rx_token == token:
            break
        # Refuse connection if we do not get the correct token.
        connection.close()

    # TODO: Replace by dataclass
    msg = msgpack.dumps({
        "type": "run_student_command",
        "student_container_id": student_container_id,
        "command": cmd,
        "teardown_script": teardown_script,
        "working_dir": working_dir,
        "ssh": ssh,
        "user": user,
        "stdin_fd": stdin,
        "stdout_fd": stdout,
        "stderr_fd": stderr
    })
    connection.send(len(msg).to_bytes(4, 'big') + msg)
    return connection

def allow_to_send_signals(signal_handler_callback, connection, student_container_id):
    """ Allow to transfer signals """
    if signal_handler_callback is not None:
        def receive_signal(signum_s):  # send signal directly to student_container
            signum_data = str(signum_s).zfill(3).encode("utf8")
            connection.send(signum_data)
        signal_handler_callback(receive_signal)

def wait_until_finished(zmq_socket, stdin, stdout, stderr, student_container_id):
    """ Dynamically handle stdin, stdout and stderr while waiting for final message """

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


def unlink_unneeded_files(paths):
    """ Unlink unneeded files """
    for path in paths:
        try:
            os.unlink(path)
        except Exception:
            pass


def handle_ssh(sk, student_container_id, grading_sk):
    """ If ssh is required, get the id and password (generated by the student_container) and sent them to the agent.
    """
    msg_len = int.from_bytes(sk.recv(4), 'big')
    msg = msgpack.loads(sk.recv(msg_len))
    if msg["type"] == "ssh_student":
        msg = StudentSsh(
            msg["ssh_user"],
            msg['ssh_key'],
            student_container_id
        )
        grading_sk.send(ProxyToAgent(msg).serialize())
