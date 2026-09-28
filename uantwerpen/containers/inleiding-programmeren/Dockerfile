# DOCKER-VERSION 1.1.0

ARG VERSION=main
ARG REGISTRY=ghcr.io
FROM ${REGISTRY}/inginious/env-base:${VERSION} AS env-cpp

LABEL org.inginious.grading.name="inleiding-programmeren"
LABEL org.inginious.grading.agent_version=4
LABEL org.opencontainers.image.source=https://github.com/UAntwerpen/INGInious

# Install Development Tools
RUN dnf -y install dnf-utils

# Enable CodeReady Builder repository
RUN dnf -y install dnf-plugins-core && \
    dnf config-manager --set-enabled crb || true

# Install GCC 14 (supports C++20) and valgrind (used by the C++ grader for leak checks)
RUN dnf -y install gcc gcc-c++ make valgrind

# Verify GCC and valgrind
RUN gcc --version && g++ --version && valgrind --version

# Upgrade pip and install packages for Python
RUN python3 -m pip install --no-cache-dir --upgrade pip setuptools wheel \
    && python3 -m pip install --no-cache-dir \
        msgpack pyzmq jinja2 PyYAML timeout-decorator pydevd-pycharm

# -------------------------
# Verification
# -------------------------

RUN set -eux; \
    gcc --version; g++ --version; valgrind --version; python3 --version; \
    python3 -c 'import inginious_container_api, msgpack, zmq, jinja2, yaml'

