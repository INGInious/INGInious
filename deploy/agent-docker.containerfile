ARG  VERSION=latest
ARG  REGISTRY=ghcr.io

FROM ${REGISTRY}/inginious/core-base:${VERSION}

COPY inginious/agent/__init__.py inginious/agent/
COPY inginious/agent/docker_agent/ inginious/agent/docker_agent/
COPY inginious/scripts inginious/scripts

RUN dnf install -y gcc python3.11-devel

# See https://github.com/pypa/setuptools_scm/#usage-from-docker
RUN --mount=source=.git,target=.git,type=bind \
    pip3 install --no-cache-dir -e .

CMD ["sh", "-c", "python3 -m inginious.scripts.agent_docker ${BACKEND} --tmpdir=/tmp/agent_data/"]
