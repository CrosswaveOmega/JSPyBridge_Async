import os
import sys
import argparse
import shutil

import subprocess

PACKAGEJSON = '{\n\t"name": "js-modules",\n\t"description": "This folder holds the installed JS deps",\n\t"dependencies": {}\n}'


def clean():
    d = os.path.dirname(__file__)
    nm = d + "/js/node_modules/"
    nl = d + "/js/package-lock.json"
    np = d + "/js/package.json"
    print("Deleting", nm, nl, np)

    try:
        shutil.rmtree(nm)
    except Exception:
        pass

    try:
        os.remove(nl)
    except Exception:
        pass

    try:
        os.remove(np)
    except Exception:
        pass


def update(args):
    print("Updating package store")
    os.chdir(os.path.dirname(__file__) + "/js")
    os.system("npm update")


def install(args):
    os.chdir(os.path.dirname(__file__) + "/js")

    if not os.path.exists("package.json"):
        with open("package.json", "w", encoding="utf8") as f:
            f.write(PACKAGEJSON)
    packagelen = len(args.packages)
    for e, package in enumerate(args.packages):
        print(f"{e}/{packagelen}: installing {package}")
        os.system(f"npm install {package}")


def uninstall(args):
    os.chdir(os.path.dirname(__file__) + "/js")

    if os.path.exists("package.json"):
        packagelen = len(args.packages)
        for e, package in enumerate(args.packages):
            print(f"{e}/{packagelen}: uninstalling {package}")
            os.system(f"npm uninstall {package}")
    else:
        print("No packages are currently installed")


def add_packages_to_file(package_list, filename="nodemodules.txt"):
    """
    Add a list of valid npm packages to a text file, skipping any package already listed.
    """
    with open(filename, "a+") as file:
        file.seek(0)
        existing_packages = set(line.strip() for line in file)
        new_packages = set(package_list) - existing_packages
        file.writelines(package + "\n" for package in new_packages)


def hybridize_dir():
    if os.path.isfile("nodemodules.txt"):
        with open("nodemodules.txt", "r", encoding="utf8") as file:
            toinstall = []
            for line in file:
                toinstall.append(line)
            size = len(toinstall)
            print(f"Installing {size} packages from {file.name}...")
            for e, line in enumerate(toinstall):
                print(f"installing npm package {e}/{size}: {line}")
                os.system(f"npm install {line.strip()}")
    else:
        print("No nodemodules.txt was detected!  ")


def hybridize(args):
    if args.action == "add":
        add_packages_to_file(args.files)
    elif args.action == "clear":
        print("clearing packages")
        if not os.path.isfile("package_lock.json"):
            os.remove("package_lock.json")
        if os.path.exists("node_modules"):
            shutil.rmtree("node_modules")
    elif args.action == "update":
        os.system("npm update")
    elif args.action == "install":
        print("hybridize me, captain.")
        hybridize_dir()
    else:
        print("invalid argument for hybridize mode.")
