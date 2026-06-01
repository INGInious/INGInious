# DOCKER-VERSION 1.1.0
FROM    rockylinux/rockylinux:10 AS env-base

ENV LANG en_US.UTF-8  
ENV LANGUAGE en_US:en  
ENV LC_ALL en_US.UTF-8

LABEL org.opencontainers.image.source=https://github.com/INGInious/containers
LABEL org.opencontainers.image.description="Base INGInious grading environment."
LABEL org.inginious.grading.agent_version=4

ARG LIB_PATH="/usr/lib/python3.12/site-packages"

# Install python, needed for scripts used in INGInious + locale support
RUN     dnf clean metadata && \
        dnf -y install langpacks-en glibc-langpack-en && \
        dnf -y install epel-release && \
        dnf -y upgrade && \
        dnf -y install python3 python3-pip python3-devel zip unzip tar sed openssh-server openssl bind-utils iproute file jq procps-ng man curl net-tools screen nano bc  && \
        pip3 install msgpack pyzmq jinja2 PyYAML timeout-decorator ipython mypy pydevd-pycharm && \
        dnf clean all

# Allow to run commands
ADD     . /INGInious
RUN     chmod -R 755 /INGInious/bin && \
        chmod 700 /INGInious/bin/INGInious && \
        mv /INGInious/bin/* /bin

# Install everything needed to allow INGInious' python libs to be loaded
RUN     chmod -R 644 /INGInious/inginious_container_api && \
        mkdir -p "${LIB_PATH}"/inginious_container_api && \
        cp -R /INGInious/inginious_container_api/*.py  "${LIB_PATH}"/inginious_container_api && \
        echo "inginious_container_api" > "${LIB_PATH}"/inginious_container_api.pth

# This maintains backward compatibility
RUN     mkdir -p "${LIB_PATH}"/inginious && \
        cp -R /INGInious/inginious_container_api/*.py  "${LIB_PATH}"/inginious && \
        echo "inginious" > "${LIB_PATH}"/inginious.pth

# Delete unneeded folders
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
LABEL org.inginious.grading.name="python3"
