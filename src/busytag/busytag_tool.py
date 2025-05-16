#!/usr/bin/env python
# SPDX-License-Identifier: MIT

from absl import app, flags

from os.path import basename, expanduser

from .config import ToolConfig
from .device import Device
from .types import *

FLAGS = flags.FLAGS
flags.DEFINE_string('config_file', '~/.busytag.toml', 'Config file path')
flags.DEFINE_string('device', None, 'Busy Tag\'s serial port.')
flags.DEFINE_integer('baudrate', 115200, 'Connection baudrate.')

def format_size(size: int) -> str:
    if size < 1_000:
        return f'{size} B'
    if size < 500_000:
        return f'{size/1_000:.2f} kB'
    return f'{size/1_000_000:.2f} MB'


def main(argv):
    config = ToolConfig(FLAGS.config_file)
    if FLAGS.device is not None:
        config.device = FLAGS.device
    if config.device is None:
        raise Exception('Device must be specified')

    bt = Device(config.device, baudrate=FLAGS.baudrate)
    print(f'Connected to {bt.name}')

    # Remove argv[0]
    argv.pop(0)

    while len(argv) > 0:
        command = argv.pop(0)

        match command:
            case 'list_pictures':
                print('Pictures in device:')
                for picture in bt.list_pictures():
                    print(f'  {picture.name} ({format_size(picture.size)})')
                print(f'Available space: {format_size(bt.get_free_storage())}')

            case 'list_files':
                print('Files in device: ')
                for file in bt.list_files():
                    print(f'  {file.name} ({file.type.value} - {format_size(file.size)})')
                print(f'Available space: {format_size(bt.get_free_storage())}')

            case 'set_picture':
                assert len(argv) >= 1
                bt.set_active_picture(argv.pop(0))

            case 'put':
                assert len(argv) >= 1
                filename = expanduser(argv.pop(0))
                with open(filename, 'rb') as fp:
                    bt.upload_file(basename(filename), fp.read())

            case 'get':
                assert len(argv) >= 1
                filename = argv.pop(0)
                data = bt.read_file(filename)
                with open(filename, 'wb') as fp:
                    fp.write(data)

            case 'rm':
                assert len(argv) >= 1
                filename = argv.pop(0)
                bt.delete_file(filename)

            case 'set_led_solid_color':
                assert len(argv) >= 1
                led_config = LedConfig(LedPin.ALL, argv.pop(0))
                bt.set_led_solid_color(led_config)

            case 'get_brightness':
                print(f'Brightness: {bt.get_display_brightness()}')

            case 'set_brightness':
                assert len(argv) >= 1
                brightness = int(argv.pop(0))
                assert 0 < brightness <= 100
                bt.set_display_brightness(brightness)

            case _:
                print(f'Unknown command: {command}')

    config.write_to_file()

if __name__ == '__main__':
    app.run(main)