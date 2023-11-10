import os
import sys
import argparse
import shutil
from commands import (
    clean,
    update,
    install,
    uninstall,
    hybridize
)

def main():
    parser = argparse.ArgumentParser(
        description="javascriptasync (JSPyBridgeAsync) package manager. Use this to clear or update the internal package store."
    )

    subparsers = parser.add_subparsers(dest="command")

    clean_parser = subparsers.add_parser("clean", help='Clean the package store')
    clean_parser.set_defaults(func=clean)

    update_parser = subparsers.add_parser("update", help='Update the package store')
    update_parser.set_defaults(func=update)

    install_parser = subparsers.add_parser("install", help='Install package(s) to the package store')
    install_parser.add_argument("packages", nargs='+')
    install_parser.set_defaults(func=install)

    uninstall_parser = subparsers.add_parser("uninstall",help='uninstall package(s) from the package store')
    uninstall_parser.add_argument("packages", nargs='+')
    uninstall_parser.set_defaults(func=uninstall)

    hybridize_parser = subparsers.add_parser("hybridize")
    hybridize_parser.add_argument("action", choices=['reset', 'install', 'add'])

    if "add" in hybridize_parser.parse_args().action:
        hybridize_parser.add_argument("files", nargs='+')

    hybridize_parser.set_defaults(func=hybridize)
    args = parser.parse_args()

    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help(sys.stderr)

if __name__ == "__main__":
    main()
