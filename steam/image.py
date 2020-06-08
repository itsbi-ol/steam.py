# -*- coding: utf-8 -*-

"""
The MIT License (MIT)

Copyright (c) 2020 James

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

Based on https://github.com/Rapptz/discord.py/blob/master/discord/file.py
"""

import hashlib
import imghdr
import io
import struct
from time import time
from typing import Union

import aiohttp

__all__ = (
    'Image',
)


class Image:
    """A wrapper around common image files. Used for :meth:`steam.User.send`.

    Parameters
    ----------
    fp: Union[:class:`io.BufferedIOBase`, :class:`aiohttp.StreamReader`, :class:`str`]
        An image or path-like to pass to :func:`open`.
    spoiler: :class:`bool`
        Whether or not to mark the image as a spoiler.


    .. note::
        Currently supported image types include:
            - PNG
            - JPG/JPEG
            - GIF
    """

    # TODO add support for "webm", "mpg", "mp4", "mpeg", "ogv"

    __slots__ = ('fp', 'spoiler', 'name', 'width', 'height', 'type', 'hash')

    def __init__(self, fp: Union[io.IOBase, aiohttp.StreamReader, str], *, spoiler: bool = False):
        self.fp = fp
        self.spoiler = spoiler

        if isinstance(fp, io.IOBase):
            if not (fp.seekable() and fp.readable()):
                raise ValueError(f'file buffer {fp!r} must be seekable and readable')
            self.fp = fp
        elif isinstance(fp, aiohttp.StreamReader):
            exc = fp.exception()
            if exc is not None:
                raise ValueError('aiohttp.StreamReader cannot be read due to an exception') from exc
            self.fp = fp
        else:
            self.fp = open(fp, 'rb')

        if len(self) > 10485760:
            raise ValueError('file is too large to upload')

        # from https://stackoverflow.com/questions/8032642
        head = self.fp.read(24)
        if len(head) != 24:
            raise ValueError('opened file has no headers')
        self.type = imghdr.what(None, head)
        if self.type == 'png':
            check = struct.unpack('>i', head[4:8])[0]
            if check != 0x0d0a1a0a:
                raise ValueError("opened file's headers do not match a standard PNG's headers")
            width, height = struct.unpack('>ii', head[16:24])
        elif self.type == 'gif':
            width, height = struct.unpack('<HH', head[6:10])
        elif self.type == 'jpeg':
            try:
                self.fp.seek(0)  # read 0xff next
                size = 2
                ftype = 0
                while not 0xc0 <= ftype <= 0xcf or ftype in (0xc4, 0xc8, 0xcc):
                    self.fp.seek(size, 1)
                    byte = self.fp.read(1)
                    while ord(byte) == 0xff:
                        byte = self.fp.read(1)
                    ftype = ord(byte)
                    size = struct.unpack('>H', self.fp.read(2))[0] - 2
                # we are at a SOFn block
                self.fp.seek(1, 1)  # skip `precision' byte.
                height, width = struct.unpack('>HH', self.fp.read(4))
            except Exception as exc:
                raise ValueError from exc
        else:
            raise TypeError('unsupported file type passed')
        self.width = width
        self.height = height
        self.hash = hashlib.sha1(self.read()).hexdigest()
        self.name = f'{int(time())}_{getattr(self.fp, "name", f"image.{self.type}")}'

    def __len__(self):
        return len(self.read())

    def read(self) -> bytes:
        self.fp.seek(0)
        read = self.fp.read()
        self.fp.seek(0)
        return read


def test_jpeg(h, _):  # adds support for more header types
    # SOI APP2 + ICC_PROFILE
    if h[0:4] == '\xff\xd8\xff\xe2' and h[6:17] == b'ICC_PROFILE':
        return 'jpeg'
    # SOI APP14 + Adobe
    if h[0:4] == '\xff\xd8\xff\xee' and h[6:11] == b'Adobe':
        return 'jpeg'
    # SOI DQT
    if h[0:4] == '\xff\xd8\xff\xdb':
        return 'jpeg'


imghdr.tests.append(test_jpeg)