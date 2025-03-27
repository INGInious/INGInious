#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.
#

""" Creates configuration file for the various frontends """

import argparse

import inginious.frontend.installer

def main():
    parser = argparse.ArgumentParser(description='Creates a configuration file for the specified frontend.')
    parser.add_argument("--file", help="Path to configuration file. If not set, use the default for the given frontend.")
    parser.add_argument("--default", action='store_true', default=False, help="Set all questions to default value.")
    args = parser.parse_args()

    inginious.frontend.installer.Installer(args.file, args.default).run()


if __name__ == "__main__":
    main()