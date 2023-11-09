# Import necessary libraries
import os, sys, argparse, shutil

# Define the JSON package details
PACKAGEJSON = (
    '{\n\t"name": "js-modules",\n\t"description": "This folder holds the installed JS deps",\n\t"dependencies": {}\n}'
)

# Initialize argparse object and define the arguments
parser = argparse.ArgumentParser(
    description="javascript (JSPyBridge) package manager. Use this to clear or update the internal package store."
)
parser.add_argument("--clean", default=False, action="store_true")
parser.add_argument("--update", default=False, action="store_true")
parser.add_argument("--install", default=False, action="store")
parser.add_argument("--uninstall", default=False, action="store")
parser.add_argument("--hybridize", default=False, action="store")
args = parser.parse_args()

# Perform actions according to the provided arguments
if args.clean:
    d = os.path.dirname(__file__)
    nm = d + "/js/node_modules/"
    nl = d + "/js/package-lock.json"
    np = d + "/js/package.json"
    print("Deleting", nm, nl, np)
    # Try to remove node_modules folder
    try:
        shutil.rmtree(nm)
    except Exception:
        pass
    # Try to remove package-lock.json file
    try:
        os.remove(nl)
    except Exception:
        pass
    # Try to remove package.json file
    try:
        os.remove(np)
    except Exception:
        pass
elif args.update:
    # Updating the package store
    print("Updating package store")
    os.chdir(os.path.dirname(__file__) + "/js")
    os.system("npm update")
elif args.install:
    # Installing a package
    os.chdir(os.path.dirname(__file__) + "/js")
    if not os.path.exists("package.json"):
        # Create package.json if not exists
        with open("package.json", "w", encoding='utf8') as f:
            f.write(PACKAGEJSON)
    os.system(f"npm install {args.install}")
elif args.uninstall:
    # Uninstalling a package
    os.chdir(os.path.dirname(__file__) + "/js")
    if os.path.exists("package.json"):
        os.system(f"npm uninstall {args.uninstall}")
    else:
        # Print message if no package installed
        print("No packages are currently installed")
elif args.hybridize:
    print('hybridize me, captain.')
    if args.hybridize[0]=='reset':
        if not os.path.isfile('package_lock.json'):
            os.remove('package_lock.json')
        if os.path.exists('node_modules'):
            shutil.rmtree('node_modules')
    if os.path.isfile('nodemodules.txt'):
        with open("nodemodules.txt", "r",encoding='utf8') as file:
            for line in file:
                print(f'installing {line}')
                os.system(f"npm install {line.strip()}")
    else:
        print('No nodemodules.txt was detected!')
else:
    # Print help message if no argument provided
    parser.print_help(sys.stderr)