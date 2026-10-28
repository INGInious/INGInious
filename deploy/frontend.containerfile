ARG  VERSION=latest
ARG  REGISTRY

FROM ${REGISTRY}/inginious/core-base:${VERSION}

# Ensure common/ matches this build, not the (possibly stale) base image layer.
COPY inginious/__init__.py inginious/
COPY inginious/common/ inginious/common/
COPY inginious/frontend inginious/frontend/
COPY inginious/client inginious/client/
COPY inginious-webapp .

RUN dnf install -y git gcc python39-devel

# See https://github.com/pypa/setuptools_scm/#usage-from-docker
RUN --mount=source=.git,target=.git,type=bind \
    pip3 install --no-cache-dir -e .

COPY deploy/db_setup.py /tmp/db_setup.py

CMD ["sh", "-c", "python3 /tmp/db_setup.py; python3 inginious-webapp"]
