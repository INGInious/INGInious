import asyncio
import os

import docker
import pytest

from inginious.agent.docker_agent.messages import AgentInitGrading, _MsgBase, MsgType, GradingStatus, StudentStarted
from inginious.agent.docker_agent.common import GRADING_CONTAINER_TCP_PORT

if (TEST_AUTO_REMOVE := os.environ.get('TEST_AUTO_REMOVE')) is None:
    TEST_AUTO_REMOVE = True
else:
    if TEST_AUTO_REMOVE == 'False':
        TEST_AUTO_REMOVE = False
    else:
        TEST_AUTO_REMOVE = True

@pytest.fixture
def docker_client():
    client = docker.from_env()
    if (
        (net := client.networks.get('bridge')) is None or
        (ipam := net.attrs.get('IPAM')) is None or
        (cfg := ipam.get('Config')) is  None or
        (gw := cfg[0].get('Gateway')) is None
    ):
        return None
    return (client, gw)

@pytest.fixture
async def start_runner(start_agent, request):

    (client, agent_ip, rx, tx) = start_agent
    print('Starting grading container.')
    # Detach container and wait for its end in a dedicated thread.
    container = client.containers.run(
        "ghcr.io/inginious/env-base:main",
        environment={
            'DEBUGGER': False,
            'AGENT_IP': agent_ip
        },
        volumes={f'{request.param}': {'bind': '/task/run', 'mode': 'rw'}},
        auto_remove=TEST_AUTO_REMOVE,
        stderr=True,
        detach=True,
        ipc_mode="shareable",
    )
    
    # Not awaited, future is passed to test in order to check container status.
    loop = asyncio.get_event_loop()
    grading = loop.run_in_executor(
        None,
        lambda: container.wait()
    )

    yield (rx, tx, grading)

    # Unconditional container cleanup
    container.kill()

@pytest.fixture
def cleanup(docker_client):
    """ Ensures that no container is running before launching the tests. """
    (client, _) = docker_client
    for container in client.containers.list():
        container.kill()

@pytest.fixture
async def start_agent(docker_client, cleanup, request):
    # Queues to proxy messages from the grading container to the tests and back.
    rx = asyncio.Queue()
    tx = asyncio.Queue()

    # Configurable grading container initialisation.
    init = request.param

    async def agent_handler(r, w):
        """ A simple Agent mock that proxies messages received from the grading
            container to `rx` and the test responses from `tx` to the grading
            container.
            The actual behavior is implemented through test functions.
        """
        print('Grading container connected to Agent.')

        # Initialise grading container.
        w.write(init().serialize())
        print("Agent initializes grading container.")

        while True:
            # Wait for grading container request
            raw = await r.read(100_000_000) 
            req = _MsgBase.deserialize(raw)
            print(f'Agent rx: {req}')
            await rx.put(req)

            resp = await tx.get()
            if resp is None:
                # EOF to stop Agent.
                break
            print(f'Agent tx: {resp}')
            w.write(resp.serialize())

    async def run_agent(client, agent_ip, agent_serves):
        print(f'\nCreating Agent endpoint at {agent_ip}:{GRADING_CONTAINER_TCP_PORT}')

        # We parametrise the actual Agent behavior according to the running test.
        # We highjack the function signature to add an asyncio queue to forward client
        # response to the test functions.
        # cb = functools.partial(request.param, rx=rx, tx=tx)
        server = await asyncio.start_server(
            agent_handler,
            host=agent_ip,
            port=GRADING_CONTAINER_TCP_PORT
        )
        while not server.is_serving():
            await asyncio.sleep(1)
        agent_serves.set_result(True)
        await server.wait_closed()

    loop = asyncio.get_event_loop()
    if docker_client is None:
        return None
    (client, agent_ip) = docker_client

    # Create a mocking Agent to test runner behavior.
    agent_serves = loop.create_future()
    _agent_task = loop.create_task(run_agent(client, agent_ip, agent_serves))

    # Wait for Agent server to serve.
    await agent_serves
    print('Agent serves.')

    return (client, agent_ip, rx, tx)

def normal_grading_init():
    return AgentInitGrading({}, {}, None )

def debug_grading_init():
    return AgentInitGrading({}, {}, None, debug=True)

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "start_agent, start_runner, debug",
    [
        (normal_grading_init, f'{os.getcwd()}/runfiles/simple_run', False),
        (debug_grading_init, f'{os.getcwd()}/runfiles/simple_run', True),
    ],
    indirect=['start_agent', 'start_runner']
)
async def test_simple_grading(start_runner, debug):
    """
        Test a simple run file with or without the optionnal parameters of the
        grading result.
    """
    rx, tx, grading = start_runner

    # Wait for grading container response to simple init.
    req = await rx.get()
    # Stop mock Agent.
    await tx.put(None)

    # Ensure that the 
    assert req.type == MsgType.GradingResult
    assert req.status == GradingStatus.Success
    assert req.text == "Sample feedback."
    assert req.problems == {}
    assert req.tests == {}

    if debug:
        assert req.stdout == 'Hello World!\n'
        assert req.stderr == 'Hello World but on stderr.\n'
    else:
        assert req.stdout is None
        assert req.stderr is None

    # FIXME: Check archive content.
    assert isinstance(req.archive, str)

    # Ensure that grading container successfully ran.
    await grading
    grading = grading.result()
    assert grading['StatusCode'] == 0

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "start_agent, start_runner, debug",
    [
        (debug_grading_init, f'{os.getcwd()}/runfiles/simple_student_run', True),
        # (debug_grading_init, f'{os.getcwd()}/runfiles/simple_run', True),
    ],
    indirect=['start_agent', 'start_runner']
)
async def test_simple_invalid_student(start_runner, debug):
    """
        Test a simple run file with or without the optionnal parameters of the
        grading result.
    """
    rx, tx, grading = start_runner

    # Wait for grading container response to simple init.
    req = await rx.get()

    # Ensure that the 
    assert req.type == MsgType.StudentRun
    assert req.token is not None
    assert isinstance(req.token, bytes)
    assert not req.ssh
    assert not req.run_as_root
    # TODO: check remaining fields

    # Mock Agent response with invalid input.
    resp = StudentStarted(0, 0)
    await tx.put(resp)

    # Grading container should answer with invalid parameters.
    err = await rx.get()
    assert err.type == MsgType.GradingError
    
    # Ensure that grading container failed with correct error.
    print("before")
    await grading
    print("after")
    grading = grading.result()
    assert grading['StatusCode'] == 254
