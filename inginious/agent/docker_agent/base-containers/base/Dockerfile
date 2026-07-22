# DOCKER-VERSION 1.1.0
FROM    rockylinux/rockylinux:10

ENV LANG en_US.UTF-8  
ENV LANGUAGE en_US:en  
ENV LC_ALL en_US.UTF-8

LABEL org.opencontainers.image.source=https://github.com/INGInious/containers
LABEL org.opencontainers.image.description="Base INGInious grading environment."

LABEL org.inginious.grading.agent_version=3

ARG PYTHON_VERSION="3.12"
ARG LIB_PATH="/usr/lib/python${PYTHON_VERSION}/site-packages"
ARG API_PATH="${LIB_PATH}/inginious_container_api"

# Install python, needed for scripts used in INGInious + locale support
RUN     dnf clean metadata && \
        dnf -y install langpacks-en glibc-langpack-en && \
        dnf -y install epel-release && \
        dnf -y upgrade && \
        dnf -y install python${PYTHON_VERSION} python${PYTHON_VERSION}-pip python${PYTHON_VERSION}-devel zip unzip tar sed openssh-server openssl bind-utils iproute file jq procps-ng man curl net-tools screen nano bc  && \
        pip${PYTHON_VERSION} install msgpack pyzmq jinja2 PyYAML timeout-decorator ipython mypy pydevd-pycharm && \
        dnf clean all

# Allow to run commands
ADD     ./base-containers/base/ /INGInious
RUN     chmod -R 755 /INGInious/bin && \
        chmod 700 /INGInious/bin/INGInious && \
        mv /INGInious/bin/* /bin

# Install everything needed to allow INGInious' python libs to be loaded
RUN     chmod -R 644 /INGInious/inginious_container_api && \
        mkdir -p "${API_PATH}" && \
        cp -R /INGInious/inginious_container_api/*.py  "${API_PATH}" && \
        echo "inginious_container_api" > "${LIB_PATH}"/inginious_container_api.pth

# This maintains backward compatibility
RUN     mkdir -p "${LIB_PATH}"/inginious/agent/docker_agent && \
        cp -R /INGInious/inginious_container_api/*.py  "${LIB_PATH}"/inginious && \
        echo "inginious" > "${LIB_PATH}"/inginious.pth
COPY    ./messages.py ./common.py "${LIB_PATH}"/inginious/agent/docker_agent

# Delete unneeded folders
RUN     rm -R /INGInious

# Create worker user
RUN     groupadd --gid 4242 worker && \
        useradd --uid 4242 --gid 4242 worker --home-dir /task

# Set locale params for SSH debug
RUN     echo -e "LANG=en_US.UTF-8\nLANGUAGE=en_US:en\nLC_ALL=en_US.UTF-8" >> /etc/environment
RUN     sed -i.bak '/^AcceptEnv/ d' /etc/ssh/sshd_config

CMD ["INGInious"]
