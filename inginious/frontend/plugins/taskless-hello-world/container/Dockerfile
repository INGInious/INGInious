    ARG   VERSION=latest
    ARG   REGISTRY=ghcr.io
    FROM  ${REGISTRY}/inginious/env-base:${VERSION}

    LABEL org.opencontainers.image.description="Demo environment for taskless jobs. This envionment only returns a Hello World message."
    LABEL org.inginious.grading.name="taskless-hello-world"


    # clean and update
    RUN dnf clean metadata && \
        dnf -y upgrade

    # copy runfile to the course directory
    COPY run.py /course/run.py
