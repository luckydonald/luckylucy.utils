# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.5"
# dependencies = []
# ///
import subprocess
import sys

__author__ = 'luckydonald'


def pip_install(*args):
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', *args])
