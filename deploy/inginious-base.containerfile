# Base core container. This is not a service per-se but is used as a common layer for the core services.
FROM rockylinux/rockylinux:10

ARG PYTHON_VERSION="3.14"

RUN dnf update -y && dnf install -y python"${PYTHON_VERSION}" python"${PYTHON_VERSION}"-pip git

WORKDIR /inginious
COPY pyproject.toml README.rst ./
COPY inginious/common/ inginious/common/
COPY inginious/__init__.py inginious/

# See https://github.com/pypa/setuptools_scm/#usage-from-docker
RUN --mount=source=.git,target=.git,type=bind \
    pip"${PYTHON_VERSION}" install --no-cache-dir -e .

RUN rm /bin/python3 && ln -s /bin/python"${PYTHON_VERSION}" /bin/python3
