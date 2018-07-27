#!/usr/bin/env python3

import subprocess
import sys


def phase(name):
    size = 5
    print("=" * size, " ", name, " ", "=" * size)

def validate():
    phase("Cleaning")
    subprocess.check_call("rm -rf out/", shell=True)
    subprocess.check_call("find . -regex \".*\.py[cod]\" | xargs rm", shell=True)

    phase("Unit tests")
    subprocess.check_call(['./run_tests.py'])

    phase("Workflow")
    subprocess.check_call(['tools/workflow.sh'])

    phase("Precommit OK")


def main():
    subprocess.check_call(['git', 'stash', 'push', '-k', '-m', '"precommit hook stash"'])
    try:
        validate()
    finally:
        subprocess.check_call(['git', 'stash', 'pop'])


if __name__ == '__main__':
    main()
