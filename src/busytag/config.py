# SPDX-License-Identifier: MIT

import tomlkit
import os.path

from .types import *

from typing import Optional

class ToolConfig(object):
    def __init__(self, path: Optional[str] = None):
        self.device = None
        self.path = path
        if path is not None:
            self.path = os.path.expanduser(path)
            if os.path.exists(self.path):
                self.__load_from_file()


    def add_preset(self, picture_filename: str, led_config: LedConfig):
        pass

    def write_to_file(self):
        assert self.path is not None
        conf = {}
        if self.device is not None:
            conf['device'] = self.device
        with open(self.path, "w") as fp:
            tomlkit.dump(conf, fp)

    def __load_from_file(self):
        with open(self.path, 'rb') as fp:
            conf = tomlkit.load(fp)
            self.device = conf['device']