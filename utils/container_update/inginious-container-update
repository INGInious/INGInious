#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

import re
import docker

INFO = '\033[94m'
WARNING = '\033[33m'
FAIL = '\033[91m'
ENDC = '\033[0m'
UNDERLINE = '\033[4m'


def ask_boolean(question, default):
    while True:
        val = ask_with_default(question, ("yes" if default else "no")).lower()
        if val in ["yes", "y", "1", "true", "t"]:
            return True
        elif val in ["no", "n", "0", "false", "f"]:
            return False
        print(INFO + "Please answer 'yes' or 'no'." + ENDC)


def ask_with_default(question, default=""):
    default = str(default)
    answer = input(INFO + UNDERLINE + question + " [" + default + "]:" + ENDC + " ")
    if answer == "":
        answer = default
    return answer


def main():
    """ Updates all "stock" images (images beginning with 'ingi/inginious-') """

    try:
        from inginious import __version__
    except:
        if not ask_boolean("Are you running this on a dev version?", True):
            print(INFO + "INGInious is not installed. Read inginious documentation for installation" + ENDC)
            return
        else:
            print(INFO + "As a dev, you should build the containers manually to use the local files instead of a downloaded image" + ENDC)
            return
    
    # Get the local images
    stock_images = []
    try:
        docker_connection = docker.from_env() 
        for image in docker_connection.images.list():
            for tag in image.attrs["RepoTags"]:
                if re.match(r"^ingi/inginious-c-(base|default):v" + __version__, tag):
                    stock_images.append(tag)
    except:
        print(FAIL + "Cannot connect to Docker!" + ENDC)
        print(FAIL + "Restart this command after making sure the command `docker info` works" + ENDC)
        return

    # Minimum mandatory images are available locally, redownload ?
    if len(stock_images) != 0:
        print(" You already have minimum mandatory images for version: " + __version__)
        if ask_boolean("Do you want to re-download them ?", True):
            for image in stock_images:
                print(INFO + ("Updating %s" % image) + ENDC)
                docker_connection.images.pull(image)
            print(INFO + "Images update done" + ENDC)
            print(INFO + "Images for version " + __version__ + " were successfully re-downloaded !" + ENDC)
            return
        print("Nothing happened")
        
    # No local image, download ?
    elif len(stock_images) == 0:
        print(" You don't have local images compatible for the version " + __version__)
        if ask_boolean("Do you want to download images for version " + __version__ + " ?", "yes"):
            docker_connection.images.pull("ingi/inginious-c-base:v" + __version__) 
            docker_connection.images.pull("ingi/inginious-c-default:v" + __version__)
            print(INFO + "Images for version " + __version__ + " were successfully downloaded !" + ENDC)
            return
        print(INFO + "Nothing happened" + ENDC)


if __name__ == "__main__":
    main()
