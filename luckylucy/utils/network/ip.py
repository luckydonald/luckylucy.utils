# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=2.7"
# dependencies = [
#     "luckylucy.utils.compat",
# ]
# ///
from ..compat import py3

__author__ = 'luckydonald'


if py3:
    def binary_ip_to_str(host):
        return ".".join([str(x) for x in host])
else:
    def binary_ip_to_str(host):
        return ".".join([str(ord(x)) for x in host])