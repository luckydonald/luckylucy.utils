# -*- coding: utf-8 -*-
# /// script
# dependencies = []
#
# [tool.luckylucy]
# module = true
# ///
from luckylucy.utils.logger import logging

__author__ = 'luckydonald'

logger = logging.getLogger(__name__)
if __name__ == '__main__':
    logging.add_colored_handler(level=logging.DEBUG)
# end if
