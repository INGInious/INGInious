ARG  VERSION=main
ARG  REGISTRY=ghcr.io

FROM ${REGISTRY}/inginious/core-base:${VERSION}

ARG  PYTHON_VERSION=3.14
ENV  PYTHON_VERSION="${PYTHON_VERSION}"

COPY inginious/frontend inginious/frontend/
COPY inginious/client inginious/client/
COPY inginious/scripts inginious/scripts

# See https://github.com/pypa/setuptools_scm/#usage-from-docker
RUN  --mount=source=.git,target=.git,type=bind \
    pip"${PYTHON_VERSION}" install --no-cache-dir -e .

COPY deploy/db_setup.py /tmp/db_setup.py

CMD ["sh", "-c", "python3 /tmp/db_setup.py; python3 -m inginious.scripts.webapp"]
