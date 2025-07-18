FROM rockylinux:8

RUN dnf update -y && dnf install -y python3.11 python3.11-pip git findutils openssh-server
COPY deploy/sshd_config /etc/ssh/sshd_config
RUN ssh-keygen -A
WORKDIR /opt
RUN git clone --revision=v3.6.14 https://github.com/sitaramc/gitolite
RUN useradd -p test -m admin
RUN chown admin:admin -R gitolite
USER admin
RUN mkdir ~/bin
RUN /opt/gitolite/install -ln
COPY deploy/gitolite.pub /tmp/admin.pub
WORKDIR /home/admin
COPY deploy/gitolite.sh .
USER root
ENTRYPOINT ["./gitolite.sh"]
