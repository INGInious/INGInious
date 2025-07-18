#! /bin/bash -xe

if [[ ! -d ~/.gitolite ]]
then
 chown -R admin:admin /home/admin/repositories
 su - admin -c  "~/bin/gitolite setup -pk /tmp/admin.pub"
fi

/usr/sbin/sshd -D
