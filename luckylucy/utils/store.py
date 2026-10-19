# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "pycryptodome",
#     "usersettings",
# ]
#
# [tool.luckylucy]
# module = true
# ///

import base64

from usersettings import Settings
from Crypto import Random
from Crypto.Cipher import AES
from Crypto.Hash import MD5

__author__ = 'luckydonald'

BS = 16


def pad(s):
    return s + (BS - len(s) % BS) * chr(BS - len(s) % BS)


# end def

def un_pad(s):
    return s[:-ord(s[len(s) - 1:])]


# end def


class Store(object):
    def __init__(self, settings_name, key=None):
        if not key:
            settings = Settings(settings_name)  # store settings, password etc.
            settings.add_setting("do-not-change!", str, random())
            settings.load_settings()
            settings.save_settings()
            self.key = settings.get("do-not-change!")
        else:
            self.key = key

    def encrypt(self, raw):
        raw = pad(raw)
        iv = Random.new().read(AES.block_size)
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        return base64.b64encode(iv + cipher.encrypt(raw))

    def decrypt(self, enc):
        enc = base64.b64decode(enc)
        iv = enc[:16]
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        return un_pad(cipher.decrypt(enc[16:]))


def random():
    return MD5.new(Random.new().read(4)).hexdigest()
