# SPDX-License-Identifier: MIT

import os.path
from typing import Optional, Sequence

import tomlkit

from .types import *


class ToolConfig(object):
    def __init__(self, path: Optional[str] = None):
        self.device = None
        self.path = path
        self.led_presets = {}
        if path is not None:
            self.path = os.path.expanduser(path)
            if os.path.exists(self.path):
                self.__load_from_file()

    def write_to_file(self):
        assert self.path is not None
        conf = {}

        if self.device is not None:
            conf['device'] = self.device

        conf['led_presets'] = {}
        for name, settings in self.led_presets.items():
            preset = []
            for setting in settings:
                preset.append({'pins': int(setting.pins), 'color': setting.color})
            conf['led_presets'][name] = preset

        with open(self.path, "w") as fp:
            tomlkit.dump(conf, fp)

    def get_led_preset(self, name: str) -> Sequence[LedConfig]:
        if name not in self.led_presets:
            raise ValueError(f'LED preset {name} not found')
        return self.led_presets[name][::]

    def __load_from_file(self):
        with open(self.path, 'rb') as fp:
            conf = tomlkit.load(fp)
            if 'device' in conf:
                self.device = conf['device']

            if 'led_presets' in conf:
                for key, entry in conf['led_presets'].items():
                    self.led_presets[key] = []
                    for pattern in entry:
                        self.led_presets[key].append(LedConfig(LedPin(int(pattern['pins'])), pattern['color']))
