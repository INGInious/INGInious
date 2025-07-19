# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Some basic functions for setuptools entrypoints """
import importlib.metadata
import sys

from inginious.common.filesystems.local import LocalFSProvider
from inginious.common.filesystems.git import GitFSProvider

def get_filesystems_providers():
    """ Returns a dictionnary of {"fs_name": fs_class}, for each usable FileSystemProvider"""
    providers = {"local": LocalFSProvider, "git": GitFSProvider}
    try:
        plugged_providers = importlib.metadata.entry_points(group="inginious.filesystems")
    except:  # < python3.10
        plugged_providers = importlib.metadata.entry_points().get("inginious.filesystems", ())
    for pp in plugged_providers:
        providers[pp.name] = pp.load()
    return providers

def filesystem_from_config_dict(config_fs):
    """ Given a dict containing an entry "module" which contains a FSProvider identifier, parse the configuration and returns a fs_provider.
        Exits if there is an error.
    """
    if "module" not in config_fs:
        print("Key 'module' should be defined for the filesystem provider ('fs' configuration option)", file=sys.stderr)
        exit(1)

    filesystem_providers = get_filesystems_providers()
    if config_fs["module"] not in filesystem_providers:
        print("Unknown filesystem provider "+config_fs["module"], file=sys.stderr)
        exit(1)

    fs_class = filesystem_providers[config_fs["module"]]
    fs_args_needed = fs_class.get_needed_args()

    fs_args = {}
    for arg_name, (arg_type, arg_required, _) in fs_args_needed.items():
        if arg_name in config_fs:
            fs_args[arg_name] = arg_type(config_fs[arg_name])
        elif arg_required:
            print("fs option {} is required".format(arg_name), file=sys.stderr)
            exit(1)

    try:
        return fs_class.init_from_args(**fs_args)
    except:
        print("Unable to load class " + config_fs["module"], file=sys.stderr)
        raise

def get_args_and_filesystem(parser):
    """Given a partially configured argparse parser, containing all the wanted data BUT the filesystem, this function will configure the parser
       to get the correct FS from the commandline, and return a tuple (args, filesystem_provider).
    """
    filesystem_providers = get_filesystems_providers()

    fs_group = parser.add_mutually_exclusive_group()
    fs_group.add_argument("--tasks", help="Path to the task directory. "
                                          "By default, it is ./tasks. You must ensure that this directory is synchronized at any time"
                                          "with the backend and the client. Either this option or --fs must be indicated, but not both.",
                          type=str, default="./tasks")
    fs_group.add_argument("--fs", help="(advanced users only) Name of the FSProvider to use. Using a FSProvider will add new args to be filled. "
                                       "Either --fs or --tasks must be filled, but not both.", type=str, choices=filesystem_providers.keys())
    parser.add_argument("--fs-help", help="Display help to fill arguments for --fs. Only checked if --fs is filled.", action="store_true")

    # Partial parsing of the args, to get the value of --fs
    args = parser.parse_known_args()[0]

    # check fs
    if args.fs is not None:
        fs_class = filesystem_providers[args.fs]
        fs_args_needed = fs_class.get_needed_args()

        fs_args_group = parser.add_argument_group("FSProvider arguments")
        for arg_name, (arg_type, arg_required, arg_desc) in fs_args_needed.items():
            fs_args_group.add_argument("--fs-" + arg_name, type=arg_type, help=arg_desc, required=arg_required)
        if args.fs_help:
            parser.parse_args(["--help"])
        args = parser.parse_args()

        returned_args = {}
        for arg_name in fs_args_needed:
            val = getattr(args, ("fs-" + arg_name).replace("-", "_"))
            if val is not None:
                returned_args[arg_name] = val

        try:
            fsprovider = fs_class.init_from_args(**returned_args)
        except:
            print("Unable to load class " + args.fs, file=sys.stderr)
            raise
    else:
        # Verify that everything can finally be parsed
        args = parser.parse_args()
        fsprovider = LocalFSProvider(args.tasks)

    return args, fsprovider
