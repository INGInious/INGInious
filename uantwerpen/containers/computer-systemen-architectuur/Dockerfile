# DOCKER-VERSION 1.1.0

ARG VERSION=main
ARG REGISTRY=ghcr.io
FROM ${REGISTRY}/inginious/env-base:${VERSION} AS env-computer-systemen-architectuur

LABEL org.inginious.grading.name="computer-systemen-architectuur"
LABEL org.inginious.grading.agent_version=4
LABEL org.opencontainers.image.source=https://github.com/UAntwerpen/INGInious

# -------------------------
# UNIX shell + standard command line tools (for shell script exercises)
# -------------------------

# coreutils is left out: the base image ships coreutils-single (same commands),
# which conflicts with the full coreutils package.
RUN dnf -y install \
        bash findutils grep gawk sed diffutils which less \
        util-linux shadow-utils hostname tree psmisc vim-minimal \
    && dnf clean all

# -------------------------
# Java (OpenJDK 21 LTS, includes javac)
# -------------------------

RUN dnf -y install java-21-openjdk-devel \
    && dnf clean all

ENV JAVA_HOME=/usr/lib/jvm/java-21-openjdk

# -------------------------
# Python 3 (system python3 from env-base) + packages for the INGInious scripts
# -------------------------

RUN python3 -m pip install --no-cache-dir --upgrade pip setuptools wheel \
    && python3 -m pip install --no-cache-dir \
        msgpack pyzmq jinja2 PyYAML timeout-decorator pydevd-pycharm

# -------------------------
# Student home directory
# -------------------------

RUN mkdir -p /home/student \
    && chown worker:worker /home/student \
    && chmod 755 /home/student

# -------------------------
# Verification
# -------------------------

RUN set -eux; \
    bash --version; python3 --version; java -version; javac -version; \
    test -d /home/student; \
    python3 -c 'import inginious_container_api, msgpack, zmq, jinja2, yaml'
