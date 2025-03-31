#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

import sys
import os
import json
import sh


def print_output(text):
    for line in text.strip('\n').split('\n'):
        print('\t' + line)


def main():
    # Change current dir for source file dir
    scriptdir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(scriptdir)

    # Open configuration file
    try:
        config = json.load(open(os.environ.get('INGINIOUS_SYNC_CONFIG', 'synchronize.json'), 'r'))
        maindir = os.path.abspath(config['maindir'])
        print('\x1b[33;1m-> Synchronization dir. : ' + maindir + ' \033[0m')
    except:
        print('\x1b[31;1mERROR: Failed to load configuration file\033[0m')
        exit(1)

    # Configure git
    try:
        sh.git.config("--global", "user.name", "INGInious")
        sh.git.config("--global", "user.email", "no-reply@inginious.info.ucl.ac.be")
    except:
        print('\x1b[31;1mERROR: Failed to configure Git. Is Git installed ?\033[0m')
        exit(1)

    for repo in config['repos']:
        print('\x1b[33;1m-> Synchronizing course repository : ' + repo['course'] + ' \033[0m')
        # Add private key with ssh add
        print('\x1b[1m--> Add private key with ssh-add \033[0m')
        os.chdir(scriptdir)
        try:
            out = sh.ssh_add(os.path.abspath(repo['keyfile']))
            print_output(out.stderr.decode('utf-8'))
        except:
            print('\x1b[31;1mERROR: Failed to load keyfile, or to add it with ssh-add\033[0m')
            exit(1)


        # Check if repo must be cloned
        if not os.path.exists(maindir + "/" + repo['course']):
            print('\x1b[33;1m--> Cloning repository\033[0m')
            out = sh.git.clone(repo['url'], maindir + "/" + repo['course'])
            print_output(out.stdout.decode('utf-8'))
        else:
            print('\x1b[1m--> Synchronizing repository\033[0m')

            # Change working dir to the repo path
            os.chdir(maindir + "/" + repo['course'])

            # Add all the files to git and commit
            out = sh.git.add("-A", '.')

            # Check for something to commit
            if sh.git.status('-s'):
                out = sh.git.commit("-a", "-m", "Automatic synchronization from INGInious")
                print_output(out.stdout.decode('utf-8'))
                print_output(out.stderr.decode('utf-8'))
                if not out.exit_code == 0:
                    exit(1)

            # Pull recursively, keeping the INGInious version of changes
            out = sh.git.pull("--no-edit","-s", "recursive", "-X", "theirs")
            print_output(out.stdout.decode('utf-8'))
            print_output(out.stderr.decode('utf-8'))
            if not out.exit_code == 0:
                exit(1)

            # Push
            if repo.get("push", True):
                out = sh.git.push()

        # Remove private key with ssh add
        print('\x1b[1m--> Remove private key with ssh-add \033[0m')
        os.chdir(scriptdir)
        out = sh.ssh_add("-d", os.path.abspath(repo['keyfile']))
        print_output(out.stderr.decode('utf-8'))
        if not out.exit_code == 0:
            exit(1)


if __name__ == "__main__":
    main()