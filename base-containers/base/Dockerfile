# DOCKER-VERSION 1.1.0
FROM    rockylinux/rockylinux:10 AS env-base

ENV LANG en_US.UTF-8  
ENV LANGUAGE en_US:en  
ENV LC_ALL en_US.UTF-8

LABEL org.opencontainers.image.source=https://github.com/INGInious/containers
LABEL org.opencontainers.image.description="Base INGInious grading environment."
LABEL org.inginious.grading.agent_version=4

ARG PYTHON_VERSION=3

# Install python, needed for scripts used in INGInious + locale support
RUN     dnf clean metadata && dnf -y upgrade && dnf -y install epel-release && crb enable && \
        dnf -y install langpacks-en glibc-langpack-en python${PYTHON_VERSION} \
                       python${PYTHON_VERSION}-pip python${PYTHON_VERSION}-devel zip \
                       unzip tar sed openssh-server openssl bind-utils iproute file jq \
                       procps-ng man curl net-tools screen nano bc && \
        dnf clean all

# Install INGInious library and scripts via pyproject.toml
ADD     . /INGInious
RUN     pip${PYTHON_VERSION} install /INGInious

# Delete unneeded source folder
RUN     rm -R /INGInious

# Create worker user
RUN     groupadd --gid 4242 worker && \
        useradd --uid 4242 --gid 4242 worker --home-dir /task

# Set locale params for SSH debug
RUN     echo -e "LANG=en_US.UTF-8\nLANGUAGE=en_US:en\nLC_ALL=en_US.UTF-8" >> /etc/environment
RUN     sed -i.bak '/^AcceptEnv/ d' /etc/ssh/sshd_config

CMD ["INGInious"]

#############
# ENV-DEFAULT
#############

FROM  env-base AS env-default

LABEL org.opencontainers.image.description="Default INGInious grading environment."
LABEL org.inginious.grading.name="default"

#############
# ENV-PYTHON3
#############

FROM  env-base AS env-python3

LABEL org.opencontainers.image.description="Python 3 INGInious grading environment."
LABEL org.inginious.grading.name="python${PYTHON_VERSION}"
