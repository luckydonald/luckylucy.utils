# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.0"
# dependencies = []
# ///
""" Python 3 only logger part"""

__author__ = 'luckydonald'

def success(self, msg, *args, exc_info=False, **kwargs):
    """
    Log 'msg % args' with severity 'SUCCESS'.

    To pass exception information, use the keyword argument exc_info with
    a true value.

    logger.debug("Houston, we landed in the %s", "moon", exc_info=False)
    """
    kwargs["exc_info"] = exc_info
    self._success(msg, *args, **kwargs)