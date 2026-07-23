ARG  VERSION=main
ARG  REGISTRY=ghcr.io

FROM ${REGISTRY}/inginious/core-base:${VERSION}

ARG  PYTHON_VERSION=3.14
ENV  PYTHON_VERSION="${PYTHON_VERSION}"

COPY inginious/agent/__init__.py inginious/agent/
COPY inginious/agent/mcq_agent/ inginious/agent/mcq_agent/
COPY inginious/scripts inginious/scripts

# See https://github.com/pypa/setuptools_scm/#usage-from-docker
RUN --mount=source=.git,target=.git,type=bind \
    pip"${PYTHON_VERSION}" install --no-cache-dir -e .

CMD ["sh", "-c", "python${PYTHON_VERSION} -m inginious.scripts.agent_mcq ${BACKEND}"]
