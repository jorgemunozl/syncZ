#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, '/home/jorge/project/githubProjects/syncZ')

from client import do_sync

if __name__ == "__main__":
    print("Testing Rich progress bars...")
    do_sync()
