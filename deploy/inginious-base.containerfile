# While https://github.com/libgit2/pygit2/pull/1395 is not available through PYPI,
# we have to custom build this patched version of pygit2 which requires libgit2.
# Build libgit2 from sources as headers are not correctly included in Rocky
# Devel package and the packaged version is too old.
FROM rockylinux/rockylinux:10 AS builder
RUN dnf update -y &&\
    dnf install -y git gcc python3.12-devel python3.12-setuptools cmake openssl-devel &&\
    python3 -m pip install build

# libssh2 is a dependency of libgit2, it is not embedded in RL10.
RUN git clone -b libssh2-1.11.1 https://github.com/libssh2/libssh2.git /tmp/libssh2
WORKDIR /tmp/libssh2
RUN cmake -B bld && cmake --build bld

# Build libgit2 with libssh2 support.
RUN git clone -b v1.9.1 https://github.com/libgit2/libgit2.git /tmp/libgit2
WORKDIR /tmp/libgit2
RUN cmake -B build -DUSE_SSH=ON -DLIBSSH2_LIBRARY=/tmp/libssh2/bld/src/libssh2.so -DLIBSSH2_INCLUDE_DIR=/tmp/libssh2/include/ && cmake --build build

# Base core container. This is not a service per-se but is used as a common layer for the core services.
FROM rockylinux/rockylinux:10

RUN dnf update -y && dnf install -y python3.12 python3.12-pip git gcc python3.12-devel

WORKDIR /inginious
COPY --from=builder /tmp/libssh2/bld/src/libssh2.so* /usr/local/lib64/
COPY --from=builder /tmp/libgit2/include /usr/local/include
COPY --from=builder /tmp/libgit2/build/libgit2.* /usr/local/lib64/
COPY pyproject.toml README.rst ./
COPY inginious/common/ inginious/common/
COPY inginious/__init__.py inginious/
ENV LD_LIBRARY_PATH=/usr/local/lib64:$LD_LIBRARY_PATH

# See https://github.com/pypa/setuptools_scm/#usage-from-docker
RUN --mount=source=.git,target=.git,type=bind \
    pip3 install --no-cache-dir -e .
