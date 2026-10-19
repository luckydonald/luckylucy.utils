# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=2.7"
# dependencies = [
#     "pip",
#     "luckylucy.utils.logger",
# ]
# ///

import pip
from luckylucy.utils.logger import logging

__author__ = 'luckydonald'
logger = logging.getLogger(__name__)


def pip_install(*args):
    return pip.main(["install"].append(args))
