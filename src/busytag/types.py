# SPDX-License-Identifier: MIT

import re
from dataclasses import dataclass
from enum import Enum, IntFlag, verify, NAMED_FLAGS

rgb_re = re.compile(r'^[0-9A-F]{6}$')

__all__ = ['LedPin', 'FileEntry', 'FileEntryType', 'WifiConfig', 'LedConfig',
           'LedPatternEntry' ]


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
        assert rgb_re.match(self.color)


@dataclass(frozen=True)
class LedPatternEntry:
    pins: LedPin
    color: str
    speed: int
    delay: int

    def __post_init__(self):
        assert rgb_re.match(self.color)
        assert self.speed >= 0
        assert self.delay >= 0

    def __str__(self) -> str:
        return f'{int(self.pins)},{self.color},{self.speed},{self.delay}'
