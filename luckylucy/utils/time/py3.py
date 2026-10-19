# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.0"
# dependencies = [
#   "typing_extensions",
# ]
# ///
# noinspection
__author__ = 'luckydonald'

import datetime

from typing_extensions import Union, Generator
from pytz import timezone


def get_local_time(time: datetime.datetime, time_zone: Union[str, None] = None) -> datetime.datetime:
	if time_zone is None:
		time_zone = "Europe/Berlin" # todo: config
	return timezone('UTC').localize(time).astimezone(timezone(time_zone))


def loop_seconds_between_times(datetime1: datetime.datetime, datetime2: datetime.datetime) -> Generator[datetime.datetime, None, None]:
	delta = datetime2 - datetime1
	seconds = delta.total_seconds()
	for x in range(0, int(seconds)):
		yield datetime1 + datetime.timedelta(seconds=x)
	yield datetime2  # so loop_seconds_between_times(dat, dat) is at least called once with dat.
