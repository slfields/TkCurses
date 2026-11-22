# TkCurses - a tkinter-compatible API layer that renders to curses
# Copyright (C) 2026  Scott L. Fields
#
# SPDX-License-Identifier: GPL-3.0-only
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Memory for a hidden field's contents that can be wiped.

A Python ``str`` cannot be changed once it is made, so a password held in
one stays in memory after it is deleted, until the allocator happens to
reuse the space. A field with ``show`` set holds its contents here instead:
in memory outside Python's object heap, locked so that it is not written to
swap, and overwritten with zeros before it is given back.

The memory comes from libsodium's ``sodium_malloc`` when the system has
libsodium, which adds guard pages around it, and otherwise from an anonymous
``mmap`` locked with ``mlock`` and kept out of core dumps. Both are wiped
the same way, through a foreign call the interpreter cannot skip.

This is defence in depth, not a guarantee: something that can read the
process's memory can read the field while it holds the text, and the
interpreter copies what passes through ``str`` APIs on the way in and out.
"""

from __future__ import annotations

import contextlib
import ctypes
import ctypes.util
import mmap
import os
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Iterator

__all__ = [
    "Allocator",
    "MmapAllocator",
    "Region",
    "SecretBuffer",
    "SodiumAllocator",
    "allocator",
    "forget_lock_failure",
    "lock_failure",
]

#: Bytes per character: each is held as one 32-bit code point, so the
#: buffer indexes in constant time and nothing is ever decoded.
CHAR_BYTES = 4

_PAGE = mmap.PAGESIZE


class Region(Protocol):
    """A block of wipeable memory, ``size`` bytes long at ``address``."""

    address: int
    size: int
    locked: bool
    #: Why the memory could not be locked, when it could not.
    lock_error: str
    #: The bytes, writable, for as long as the region is open.
    view: memoryview

    def wipe(self) -> None:
        """Overwrite every byte with zero."""

    def free(self) -> None:
        """Wipe, then give the memory back. Harmless twice."""


class Allocator(Protocol):
    """Where regions come from."""

    name: str

    def allocate(self, size: int) -> Region:
        """A zeroed region of at least ``size`` bytes."""


def _libc() -> ctypes.CDLL | None:
    """The C library, through the symbols already loaded into the process:
    no search, so importing this starts no ``ldconfig``."""
    try:
        return ctypes.CDLL(None, use_errno=True)
    except OSError:  # pragma: no cover - every POSIX Python has one
        return None


_LIBC = _libc()

#: libsodium's names, tried before ``find_library``, which runs a program
#: to search for it.
_SODIUM_NAMES = (
    "libsodium.so.26",
    "libsodium.so.23",
    "libsodium.so",
    "libsodium.dylib",
)


def _errno_text() -> str:
    number = ctypes.get_errno()
    return os.strerror(number) if number else "unknown error"


class _MmapRegion:
    """An anonymous mapping: page-aligned, outside the object heap."""

    def __init__(self, size: int) -> None:
        self.size = -(-max(size, 1) // _PAGE) * _PAGE
        self._map: mmap.mmap | None = mmap.mmap(-1, self.size)
        self._anchor: ctypes.Array[ctypes.c_ubyte] | None = (
            ctypes.c_ubyte * self.size
        ).from_buffer(self._map)
        self.address = ctypes.addressof(self._anchor)
        self.view = memoryview(self._map)
        self.locked = False
        self.lock_error = ""
        if hasattr(mmap, "MADV_DONTDUMP"):  # Linux: leave it out of core dumps
            with contextlib.suppress(OSError):
                self._map.madvise(mmap.MADV_DONTDUMP)
        if _LIBC is None:
            self.lock_error = "no C library to call mlock through"
        elif _LIBC.mlock(ctypes.c_void_p(self.address), ctypes.c_size_t(self.size)):
            self.lock_error = _errno_text()
        else:
            self.locked = True

    def wipe(self) -> None:
        if self._map is not None:
            ctypes.memset(self.address, 0, self.size)

    def free(self) -> None:
        if self._map is None:
            return
        self.wipe()
        if self.locked and _LIBC is not None:
            _LIBC.munlock(ctypes.c_void_p(self.address), ctypes.c_size_t(self.size))
        self.view.release()
        self._anchor = None  # drops the export, so the map can close
        self._map.close()
        self._map = None


class MmapAllocator:
    """Anonymous ``mmap``, ``mlock`` and ``memset``: the fallback."""

    name = "mmap with mlock"

    def allocate(self, size: int) -> Region:
        return _MmapRegion(size)


class _SodiumRegion:
    """Memory from ``sodium_malloc``, between guard pages."""

    def __init__(self, sodium: ctypes.CDLL, pointer: int, size: int) -> None:
        self._sodium: ctypes.CDLL | None = sodium
        self.address = pointer
        self.size = size
        array = (ctypes.c_ubyte * size).from_address(pointer)
        self.view = memoryview(array).cast("B")
        ctypes.memset(pointer, 0, size)  # sodium_malloc fills with garbage
        self.locked = (
            sodium.sodium_mlock(ctypes.c_void_p(pointer), ctypes.c_size_t(size)) == 0
        )
        self.lock_error = "" if self.locked else _errno_text()

    def wipe(self) -> None:
        if self._sodium is not None:
            self._sodium.sodium_memzero(
                ctypes.c_void_p(self.address), ctypes.c_size_t(self.size)
            )

    def free(self) -> None:
        sodium, self._sodium = self._sodium, None
        if sodium is None:
            return
        sodium.sodium_memzero(ctypes.c_void_p(self.address), ctypes.c_size_t(self.size))
        self.view.release()
        if self.locked:
            sodium.sodium_munlock(
                ctypes.c_void_p(self.address), ctypes.c_size_t(self.size)
            )
        sodium.sodium_free(ctypes.c_void_p(self.address))


class SodiumAllocator:
    """libsodium's guarded allocations, falling back per region if one fails."""

    name = "libsodium"

    def __init__(self, sodium: ctypes.CDLL) -> None:
        sodium.sodium_malloc.restype = ctypes.c_void_p
        sodium.sodium_malloc.argtypes = [ctypes.c_size_t]
        self._sodium = sodium
        self._fallback = MmapAllocator()

    @classmethod
    def load(cls) -> SodiumAllocator | None:
        """The system's libsodium, initialised, or None if there is none."""
        for name in (*_SODIUM_NAMES, ctypes.util.find_library("sodium")):
            if name is None:
                continue
            try:
                sodium = ctypes.CDLL(name, use_errno=True)
                if sodium.sodium_init() < 0:
                    return None
            except (OSError, AttributeError):
                continue
            return cls(sodium)
        return None

    def allocate(self, size: int) -> Region:
        size = max(size, 1)
        pointer = self._sodium.sodium_malloc(size)
        if not pointer:
            return self._fallback.allocate(size)
        return _SodiumRegion(self._sodium, pointer, size)


_chosen: Allocator | None = None
_lock_failure = ""


def allocator() -> Allocator:
    """The allocator for this process: libsodium if found, else ``mmap``."""
    global _chosen
    if _chosen is None:
        _chosen = SodiumAllocator.load() or MmapAllocator()
    return _chosen


def lock_failure() -> str:
    """Why a hidden field's memory could not be locked, or "" if it always was."""
    return _lock_failure


def forget_lock_failure() -> None:
    """Clear :func:`lock_failure`, once it has been reported."""
    global _lock_failure
    _lock_failure = ""


def _allocate(size: int) -> Region:
    global _lock_failure
    region = allocator().allocate(size)
    if not region.locked and not _lock_failure:
        _lock_failure = region.lock_error or "the memory could not be locked"
    return region


def _utf8_length(code: int) -> int:
    if code < 0x80:
        return 1
    if code < 0x800:
        return 2
    if 0xD800 <= code <= 0xDFFF:
        raise ValueError("a lone surrogate cannot be written as UTF-8")
    return 3 if code < 0x10000 else 4


class SecretBuffer:
    """One line of text held in a wipeable region.

    Behaves as the ``str`` it stands for where a field needs it to -
    ``len``, one character by index - without ever building that string,
    except through :meth:`to_str`, which is the one place it is made.
    """

    def __init__(self, text: str = "") -> None:
        self._length = 0
        self._region = _allocate(max(len(text), _PAGE // CHAR_BYTES) * CHAR_BYTES)
        self._codes: memoryview | None = self._region.view.cast("I")
        self.insert(0, text)

    # ------------------------------------------------------------- reading

    def __len__(self) -> int:
        return self._length

    def __getitem__(self, index: int) -> str:
        if not -self._length <= index < self._length:
            raise IndexError("secret index out of range")
        return chr(self._live()[index % self._length])

    def to_str(self) -> str:
        """The contents as a ``str``: a copy this buffer cannot wipe."""
        codes = self._live()
        return "".join(chr(codes[i]) for i in range(self._length))

    @contextlib.contextmanager
    def utf8(self) -> Iterator[memoryview]:
        """The contents as UTF-8, in a region of their own, wiped on exit.

        The view is read-only and is released when the block ends; keeping
        it past that raises ``ValueError`` on use rather than reading
        freed memory.
        """
        codes = self._live()
        size = sum(_utf8_length(codes[i]) for i in range(self._length))
        region = _allocate(size)
        view = region.view
        try:
            at = 0
            for i in range(self._length):
                at = _encode(codes[i], view, at)
            shown = view[:size].toreadonly()
            try:
                yield shown
            finally:
                shown.release()
        finally:
            region.free()

    # ------------------------------------------------------------- editing

    def insert(self, index: int, text: str) -> None:
        """Put ``text`` in before ``index``, which is within 0 to len."""
        if not text:
            return
        added = len(text)
        self._reserve(self._length + added)
        codes = self._live()
        if index < self._length:
            base = self._region.address
            ctypes.memmove(
                base + (index + added) * CHAR_BYTES,
                base + index * CHAR_BYTES,
                (self._length - index) * CHAR_BYTES,
            )
        for offset, char in enumerate(text):
            codes[index + offset] = ord(char)
        self._length += added

    def delete(self, first: int, last: int) -> None:
        """Remove ``first`` up to ``last``, and zero what that leaves over."""
        if last <= first:
            return
        base = self._region.address
        ctypes.memmove(
            base + first * CHAR_BYTES,
            base + last * CHAR_BYTES,
            (self._length - last) * CHAR_BYTES,
        )
        removed = last - first
        self._length -= removed
        ctypes.memset(base + self._length * CHAR_BYTES, 0, removed * CHAR_BYTES)

    def clear(self) -> None:
        """Empty it, zeroing every byte."""
        self._region.wipe()
        self._length = 0

    def close(self) -> None:
        """Wipe and give back the memory. Harmless twice."""
        if self._codes is None:
            return
        self._codes.release()
        self._codes = None
        self._length = 0
        self._region.free()

    def __del__(self) -> None:
        with contextlib.suppress(Exception):
            self.close()

    # ------------------------------------------------------------ internal

    def _live(self) -> memoryview:
        if self._codes is None:
            raise ValueError("the secret has been wiped")
        return self._codes

    def _reserve(self, length: int) -> None:
        """Grow, by doubling, to hold ``length`` characters."""
        codes = self._live()
        if length <= len(codes):
            return
        capacity = len(codes)
        while capacity < length:
            capacity *= 2
        region = _allocate(capacity * CHAR_BYTES)
        ctypes.memmove(region.address, self._region.address, self._length * CHAR_BYTES)
        codes.release()
        self._region.free()
        self._region = region
        self._codes = region.view.cast("I")


def _encode(code: int, view: memoryview, at: int) -> int:
    """Write ``code`` as UTF-8 at ``at``; answer where the next one goes."""
    if code < 0x80:
        view[at] = code
        return at + 1
    if code < 0x800:
        view[at] = 0xC0 | code >> 6
        view[at + 1] = 0x80 | code & 0x3F
        return at + 2
    if code < 0x10000:
        view[at] = 0xE0 | code >> 12
        view[at + 1] = 0x80 | code >> 6 & 0x3F
        view[at + 2] = 0x80 | code & 0x3F
        return at + 3
    view[at] = 0xF0 | code >> 18
    view[at + 1] = 0x80 | code >> 12 & 0x3F
    view[at + 2] = 0x80 | code >> 6 & 0x3F
    view[at + 3] = 0x80 | code & 0x3F
    return at + 4
