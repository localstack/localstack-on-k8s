import sys

from l8k.deploy import deploy
from l8k.install import install

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(1)
    command = sys.argv[1]
    if command == "install":
        install()
    if command == "deploy":
        deploy()
