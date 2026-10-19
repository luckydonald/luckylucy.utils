# -*- coding: utf-8 -*-
# /// luckylucy-module
# dependencies = []
# ///
from luckylucy.utils.logger import logging

__author__ = 'luckydonald'

logger = logging.getLogger(__name__)


def br(text):
    """
    {{ text | br }}
    Adds html '<br>' to all '\n' linebreaks.

    :param text: input text to modify
    :type  text: str

    :return: modified text
    :rtype: str
    """
    return text.replace("\n", "<br>\n")
# end def
