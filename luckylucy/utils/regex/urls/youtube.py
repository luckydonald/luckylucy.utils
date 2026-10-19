# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.8"
# dependencies = []
# ///
import re

__author__ = 'luckydonald'
__all__ = ['YOUTUBE_URL_REGEX', '_YOUTUBE_URL_REGEX']

_YOUTUBE_URL_REGEX = r'(?:https?://)?(?:www\.)?(?:youtube\.com/(?:v/|watch\?v=|embed/)|youtu\.be/)(?P<vid>[\w-]+)(?:\S+)?'
YOUTUBE_URL_REGEX = re.compile(_YOUTUBE_URL_REGEX)
"""
:const:`YOUTUBE_URL_REGEX`: Matches youtube videos.
The matching group `vid` contains the video id.
"""
