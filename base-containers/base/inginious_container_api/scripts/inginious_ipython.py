# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

import sys
import IPython.core.interactiveshell


def main():
    if len(sys.argv) == 1:
        print("No file given", file=sys.stderr)
        sys.exit(1)

    # A small hack to force IPython to interpret the given file as a IPYthon file.
    # By default, it only parses correctly files with the .ipy extension.

    shell = IPython.core.interactiveshell.InteractiveShell()
    sys.argv = sys.argv[1:]  # correct the args

    # Add the utility function to the global namespace
    shell.run_cell("from inginious_container_api.input import *", store_history=False)
    shell.run_cell("from inginious_container_api.feedback import *", store_history=False)
    shell.run_cell("from inginious_container_api.lang import *", store_history=False)
    shell.run_cell("from inginious_container_api.rst import *", store_history=False)
    shell.run_cell("from inginious_container_api.run_student import *", store_history=False)
    shell.run_cell("from inginious_container_api.ssh_student import *", store_history=False)
    shell.run_cell("__file__ = \"" + sys.argv[0] + "\"", store_history=False)

    shell.safe_execfile_ipy(sys.argv[0])


if __name__ == "__main__":
    main()
