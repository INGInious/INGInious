ARG  VERSION=latest
ARG  REGISTRY

FROM ${REGISTRY}/inginious/core-base:${VERSION}

# Ensure common/ matches this build, not the (possibly stale) base image layer.
COPY inginious/__init__.py inginious/
COPY inginious/common/ inginious/common/
COPY inginious/agent/__init__.py inginious/agent/
COPY inginious/agent/docker_agent/ inginious/agent/docker_agent/
COPY inginious-agent-docker .

RUN dnf install -y gcc python39-devel

# See https://github.com/pypa/setuptools_scm/#usage-from-docker
RUN --mount=source=.git,target=.git,type=bind \
    pip3 install --no-cache-dir -e .

CMD ["sh", "-c", "python3 inginious-agent-docker ${BACKEND} --tmpdir=/tmp/agent_data/"]
