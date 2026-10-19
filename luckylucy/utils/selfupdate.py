# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.8"
# dependencies = []
#
# [tool.luckylucy]
# module = true
# ///
import subprocess
import sys

__author__ = 'luckydonald'

from luckylucy.utils.decorators import deprecated


@deprecated
def selfupdate():
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "luckylucy.utils"])
# end def

selfupdate()

