# SPDX-License-Identifier: MIT

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, IntFlag, verify, NAMED_FLAGS

rgb_re = re.compile(r'^[0-9A-F]{6}$')


def _normalize_color(obj, color: str) -> None:
    """Validates an RGB hex colour, storing it upper-cased on the (frozen) dataclass."""
    if not isinstance(color, str) or not rgb_re.match(color.upper()):
        raise ValueError(f'Invalid colour {color!r}: expected 6 hex digits (e.g. FF0000)')
    object.__setattr__(obj, 'color', color.upper())

__all__ = ['LedPin', 'FileEntry', 'FileEntryType', 'WifiConfig', 'LedConfig',
           'LedPatternEntry', 'ProgressListener']


@verify(NAMED_FLAGS)
class LedPin(IntFlag):
    PIN_0 = 1
    PIN_1 = 2
    PIN_2 = 4
    PIN_3 = 8
    PIN_4 = 16
    PIN_5 = 32
    PIN_6 = 64
    ALL = 127


class FileEntryType(Enum):
    FILE = 'file'
    DIRECTORY = 'dir'


@dataclass(frozen=True)
class FileEntry:
    """File stored in the Busy Tag device."""
    name: str
    size: int
    type: FileEntryType = FileEntryType.FILE


@dataclass(frozen=True)
class WifiConfig:
    """Wifi configuration."""
    ssid: str
    password: str


@dataclass(frozen=True)
class LedConfig:
    pins: LedPin
    color: str

    def __post_init__(self):
        _normalize_color(self, self.color)


@dataclass(frozen=True)
class LedPatternEntry:
    pins: LedPin
    color: str
    speed: int
    delay: int

    def __post_init__(self):
        _normalize_color(self, self.color)
        if self.speed < 0:
            raise ValueError('speed must be non-negative')
        if self.delay < 0:
            raise ValueError('delay must be non-negative')

    def __str__(self) -> str:
        return f'{int(self.pins)},{self.color},{self.speed},{self.delay}'


class ProgressListener(ABC):
    """Interface passed to operations that (might) take a long time,
    which receives updates on the operation progress."""

    @abstractmethod
    def set_max(self, max: int) -> None:
        """Sets the size of the operation (e.g. number of bytes in a file operation).

        :param max: The max possible progress value."""
        pass

    @abstractmethod
    def goto(self, position: int):
        """Updates how far along the operation is.

        :param position: The current position of the operation."""
        pass

    @abstractmethod
    def finish(self):
        """Called when the operation has finished."""
        pass
