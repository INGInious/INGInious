# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

import argparse
import inginious_container_api.feedback


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter, description='Set the grade/score of the task.\n')
    parser.add_argument('grade', help="grade/score")
    args = parser.parse_args()

    # Do the real stuff
    inginious_container_api.feedback.set_grade(args.grade)


if __name__ == "__main__":
    main()
