"""
This module provides a command-line interface to install NPM packages 
to the javascriptasync library as a whole or your current directory.

Available commands are "clean", "update", "install", "uninstall", and "hybridize".
The "clean" command is for clearing the package store.
The "update" command updates the package store.
The "install" command installs specified package(s) to the package store.
The "uninstall" command uninstalls specified package(s) from the package store.

The "hybridize" command has a mandatory argument "action" 
which can take values 'reset', 'install', 'add', or 'update'.
An additional argument "files" can be added if "action" is set to "add".

If no function is specified in the arguments when running the script, 
it will print the help menu to stderr.
"""

import sys
import argparse
from .commands import clean, update, install, uninstall, hybridize


def main():
    parser = argparse.ArgumentParser(
        description="javascriptasync (JSPyBridgeAsync) package manager. Use this to clear or update the internal package store."
    )

    subparsers = parser.add_subparsers(dest="command")

    clean_parser = subparsers.add_parser("clean", help="Clean the package store")
    clean_parser.set_defaults(func=clean)

    update_parser = subparsers.add_parser("update", help="Update the package store")
    update_parser.set_defaults(func=update)

    install_parser = subparsers.add_parser(
        "install", help="Install package(s) to the package store"
    )
    install_parser.add_argument("packages", nargs="+")
    install_parser.set_defaults(func=install)

    uninstall_parser = subparsers.add_parser(
        "uninstall", help="uninstall package(s) from the package store"
    )
    uninstall_parser.add_argument("packages", nargs="+")
    uninstall_parser.set_defaults(func=uninstall)

    hybridize_parser = subparsers.add_parser(
        "hybridize",
        help="install a node_modules folder using the packages within a nodemodules.txt.  use install to install the packages.",
    )
    hybridize_parser.add_argument("action", choices=["clear", "install", "add", "update"])

    if "add" in sys.argv[1:]:
        hybridize_parser.add_argument("files", nargs="+")

    args = parser.parse_args(sys.argv[1:])

    if args.command == "hybridize":
        hybridize(args)
    elif hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help(sys.stderr)


if __name__ == "__main__":
    main()
