# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.
import os
import tempfile
import subprocess
import resource
import stat
import time
import logging
import array
import socket
import shlex
import struct
import asyncio
import errno
import sys
import msgpack

def set_limits_user(user):
    if user == "worker":
        os.setgid(4242)
        os.setuid(4242)
    os.environ["HOME"] = "/task"
    resource.setrlimit(resource.RLIMIT_NPROC, (1000, 1000))


def set_executable(filename):
    # When mounting the course/common/run file, the permissions of the file on the host and in the container will still be the same
    # It should therefore already be executable on the host for the moment
    # TODO: fix this problem by moving the set_executable function to the agent where temporary folder is created for example
    if not filename.startswith("/course/common"):
        st = os.stat(filename)
        os.chmod(filename, st.st_mode | stat.S_IEXEC)


def execute_process(args, stdin_string="", internal_command=False, user="worker"):
    if not isinstance(args, list):
        args = [args]
    set_limits = (lambda: set_limits_user(user))
    stdin = tempfile.TemporaryFile()
    stdin.write(stdin_string.encode('utf-8'))
    stdin.seek(0)

    stdout = tempfile.TemporaryFile()
    stderr = tempfile.TemporaryFile()
    if internal_command:
        pr = subprocess.Popen(args, stdin=stdin, stdout=stdout, stderr=stderr)
    else:
        set_executable(args[0])
        pr = subprocess.Popen(args, preexec_fn=set_limits, stdin=stdin, stdout=stdout, stderr=stderr)
    pr.wait()
    stdout.seek(0)
    stderr.seek(0)
    return stdout.read(), stderr.read()


def start_ssh_server(ssh_user):
    # Generate password
    password, _ = execute_process(["/usr/bin/openssl", "rand", "-base64", "10"], internal_command=True, user=ssh_user)
    password = password.decode('utf8').strip()
    execute_process(["/usr/bin/bash", "-c", "echo '{}:{}' | chpasswd".format(ssh_user, password)],
                    internal_command=True, user=ssh_user)
    # generate the host keys
    execute_process(["/usr/bin/ssh-keygen", "-A"], internal_command=True, user=ssh_user)

    # remove /run/nologin if it exists
    if os.path.exists("/run/nologin"):
        os.unlink("/run/nologin")

    permit_root_login = "yes" if ssh_user == "root" else "no"

    # Start the ssh server
    execute_process(["/usr/sbin/sshd",
                    "-p", "22",
                    "-o", "PermitRootLogin={}".format(permit_root_login),
                    "-o", "PasswordAuthentication=yes", "-o", "StrictModes=no",
                    "-o", "ForceCommand=echo LOGIN: Good luck !; script -q .ssh_logs; cp .ssh_logs /task/student/.ssh_logs; echo LOGOUT: Good bye!",
                    "-o", "AllowUsers={}".format(ssh_user)], internal_command=True, user=ssh_user)
    return ssh_user, password
    #When logging in, student is in a special interactive shell where everything is logged into a file.
    #When he exits this special shell, the log file is copied into the student directory and the ssh connection closes


def ssh_wait(ssh_user, timeout=None):
    """ Wait maximum 2 minutes for user ssh_user to connect.
    Wait for the user to leave. No timeout unless specified (the container has already a timeout anyway)"""
    connected_workers = 0
    attempts = 0
    while connected_workers == 0 and attempts < 120:  # wait max 2min for someone to connect
        time.sleep(1)
        stdout, stderr = execute_process(
            ["/bin/bash", "-c", "pgrep -u {} sshd-session | wc -l".format(ssh_user)], internal_command=True, user=ssh_user)
        connected_workers = int(stdout)
        attempts += 1
    attempts = 0
    if connected_workers != 0:  # If someone is connected, wait until no one remains
        while connected_workers != 0:
            if timeout is not None and attempts >= timeout:
                print("Timeout while user was still connected !")
                return 253  # timeout
            time.sleep(1)
            stdout, stderr = execute_process(
                ["/bin/bash", "-c", "pgrep -u {} sshd-session | wc -l".format(ssh_user)], internal_command=True, user=ssh_user)
            connected_workers = int(stdout)
            attempts += 1
        return 0  # The user connected and disconnected
    else:
        print("No one connected !")
        return 253  # timeout


def setup_logger():
    """ returns a logger for the current container """
    logger = logging.getLogger("inginious-student")
    logger.setLevel(logging.DEBUG)
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    return logger


def recv_fds(sock, msglen, maxfds):
    """ Receive FDs from the unix socket. Copy-pasted from the Python doc.
    Used only if both grading and student containers are using docker runtime"""
    fds = array.array("i")  # Array of ints
    msg, ancdata, _, addr = sock.recvmsg(msglen, socket.CMSG_LEN(maxfds * fds.itemsize))
    for cmsg_level, cmsg_type, cmsg_data in ancdata:
        if (cmsg_level == socket.SOL_SOCKET and cmsg_type == socket.SCM_RIGHTS):
            # Append data, ignoring any truncated integers at the end.
            fds.frombytes(cmsg_data[:len(cmsg_data) - (len(cmsg_data) % fds.itemsize)])
    return msg, list(fds)


async def write_stdout(msg, container_stdout):
    """ Helper to send messages to the agent on the container stdout stream """
    msg = msgpack.dumps(msg, use_bin_type=True)
    container_stdout.write(struct.pack('!I', len(msg)))
    container_stdout.write(msg)
    await container_stdout.drain()


def run_teardown_script(script, set_limits):
    """ Run the teardown script. Only used when a teardown script was specified """
    tear_down_process = subprocess.Popen(shlex.split(script), preexec_fn=set_limits)
    tear_down_process.wait()  # Wait for teardown_script to finish before exiting the container


def handle_signals(concerned_subprocess, com_socket):
    """ Handles signals given by run_student on the socket.
    Used only when both containres are on a shared kernel. Otherwise, it is already handled by handle_stdin function """
    while True:
        try:
            signal = com_socket.recv(3)
            if signal == b'---' or len(signal) < 3:  # quit
                return
            concerned_subprocess.send_signal(int(signal.decode('utf8')))
        except:
            sys.exit()


def handle_ssh_session(container_id, socket_unix, user):
    """ Start the ssh server and send identification information """
    ssh_user, password = start_ssh_server(user)
    # Send ssh information to the grading container
    message = msgpack.dumps({"type": "ssh_student", "ssh_user": ssh_user, "password": password})  # constant size
    message_size = struct.pack('!I', len(message))
    socket_unix.send(message_size)
    socket_unix.send(message)
   # Wait for user to connect and leave
    ssh_retval = ssh_wait(ssh_user)
    return ssh_retval


def receive_initial_command():
    """ Receive the command to run (directly from student-grading socket if both dockers or via the agent otherwise)"""
    # Connect to the socket
    my_socket = socket.socket(socket.AF_UNIX)  # , socket.SOCK_CLOEXEC) # for linux only
    my_socket.connect("/__parent.sock")
    # Say hello
    print("Saying hello")
    my_socket.send(b'H')
    print("Said hello")
    # Receive fds
    print("Receiving fds")
    msg, fds = recv_fds(my_socket, 1, 3)
    assert msg == b'S'
    print("Received fds")
    # Unpack the start message
    print("Unpacking start cmd")
    unpacker = msgpack.Unpacker()
    start_cmd = None
    while start_cmd is None:
        data = my_socket.recv(1)
        unpacker.feed(data)
        for msg in unpacker:
            if msg["type"] == "run_student_command":
                return my_socket, fds, msg
            raise Exception("Received wrong initial message")
 

def read_block(bin_file, chunk_size):
    """ Returns a chunk of size up to chunk_size bytes """
    chunk = bin_file.read(chunk_size)
    while not chunk:
        chunk_size = chunk_size // 2
        chunk = bin_file.read(chunk_size)
        if len(chunk) == 0:  # Only happens when the bin_file (pipe) is closed
            return False
    return chunk

def scripts_isolation(isolate):
    """ Make the script directory isolated or not from the student """
    if isolate:
        os.chmod("/task/student/scripts", 000)
    else:
        os.chmod("/task/student/scripts", 777)

