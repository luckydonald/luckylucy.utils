#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=2.7"
# dependencies = [
#     "teleflask",
#     "luckylucy.utils.logger",
# ]
# ///
from luckylucy.utils.logger import logging
from teleflask import TBlueprint
from .sticker import sticker_crawl_tbp

__author__ = 'luckydonald'

logger = logging.getLogger(__name__)
if __name__ == '__main__':
    logging.add_colored_handler(level=logging.DEBUG)
# end if


crawl_tbp = TBlueprint(__name__)

crawl_tbp.register_tblueprint(sticker_crawl_tbp)
