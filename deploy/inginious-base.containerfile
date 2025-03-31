# Base core container. This is not a service per-se but is used as a common layer for the core services.
FROM rockylinux:8

RUN dnf update -y && dnf install -y python3.11 python3.11-pip git

WORKDIR /inginious
COPY pyproject.toml README.rst ./
COPY inginious/common/ inginious/common/
COPY inginious/__init__.py inginious/

# See https://github.com/pypa/setuptools_scm/#usage-from-docker
RUN --mount=source=.git,target=.git,type=bind \
    pip3 install --no-cache-dir -e .
