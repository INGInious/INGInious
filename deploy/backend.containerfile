ARG  VERSION=latest
ARG  REGISTRY=ghcr.io

FROM ${REGISTRY}/inginious/core-base:${VERSION}

COPY inginious/backend/ inginious/backend/
COPY inginious/scripts/ inginious/scripts/

# See https://github.com/pypa/setuptools_scm/#usage-from-docker
RUN --mount=source=.git,target=.git,type=bind \
    pip3 install --no-cache-dir -e .

CMD ["sh", "-c", "python3 -m inginious.scripts.backend ${AGENT} ${CLIENT}"]
