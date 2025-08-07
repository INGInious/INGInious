FROM rockylinux/rockylinux:10

RUN dnf update -y && dnf install -y python3.12 python3.12-pip git findutils openssh-server perl-core
COPY deploy/sshd_config /etc/ssh/sshd_config
RUN ssh-keygen -A
WORKDIR /opt
RUN git clone -b v3.6.14 https://github.com/sitaramc/gitolite
RUN useradd -p test -m admin
RUN chown admin:admin -R gitolite
USER admin
RUN git config --global init.defaultBranch main
RUN mkdir ~/bin
RUN /opt/gitolite/install -ln
COPY deploy/gitolite.pub /tmp/superadmin.pub
WORKDIR /home/admin
COPY deploy/gitolite.sh .
USER root
ENTRYPOINT ["./gitolite.sh"]
