# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

import os
import sys
import shutil
import argparse


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter, description='Manage file archive.\n')
    parser.add_argument('-a', '--add', help="add file to archive", default="")
    parser.add_argument('-r', '--remove', help="remove file from archive", default="")
    parser.add_argument('-s', '--subdir', dest='outsubdir', help="output subfolder in archive directory", default="")
    args = parser.parse_args()

    addfile = args.add
    rmfile = args.remove
    outsubdir = args.outsubdir

    if addfile:
        try:
            os.makedirs('/archive/' + outsubdir)
        except OSError:
            pass
        
        try:    
            shutil.copy(addfile, '/archive/' + outsubdir + '/' + os.path.basename(addfile))
        except IOError as e:
            print(e)
            sys.exit(2)

    if rmfile:
        try:
            os.remove('/archive/' + outsubdir + '/' + rmfile)
        except IOError as e:
            print(e)
            sys.exit(2)


if __name__ == "__main__":
    main()
