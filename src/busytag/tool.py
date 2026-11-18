#!/usr/bin/env python
# SPDX-License-Identifier: MIT
from os.path import basename, expanduser, exists
from typing import List, Optional

from absl import app, flags
from progress.bar import Bar

from .config import ToolConfig
from .device import Device, list_devices
from .busytag_types import *

FLAGS = flags.FLAGS
flags.DEFINE_string('config_file', '~/.busytag.toml', 'Config file path')
flags.DEFINE_string('device', None, 'Busy Tag\'s serial port.')
flags.DEFINE_integer('baudrate', 115200, 'Connection baudrate.')

class ProgressBar(Bar, ProgressListener):
    suffix = '%(position_bytes)s / %(total_bytes)s - %(eta)ds'

    @property
    def position_bytes(self) -> str:
        return format_size(self.index)

    @property
    def total_bytes(self) -> str:
        return format_size(self.max)

    def set_max(self, max: int) -> None:
        self.max = max
        self.start()


def format_size(size: int) -> str:
    if size < 1_000:
        return f'{size} B'
    if size < 500_000:
        return f'{size / 1_000:.2f} kB'
    return f'{size / 1_000_000:.2f} MB'


class UsageError(Exception):
    """Raised when a command is invoked with missing or invalid arguments."""


def pop_arg(argv: List[str], command: str, arg_name: str) -> str:
    """Pops the next positional argument, or raises UsageError if there is none."""
    if len(argv) == 0:
        raise UsageError(f'Command `{command}` requires argument <{arg_name}>')
    return argv.pop(0)


def main(argv: List[str]) -> Optional[int]:
    try:
        return run_command(argv)
    except UsageError as e:
        print(f'Error: {e}')
        return 1


def run_command(argv: List[str]) -> Optional[int]:
    config = ToolConfig(FLAGS.config_file)
    if FLAGS.device is not None:
        config.device = FLAGS.device
    config.write_to_file()
    bt: Optional[Device] = None

    # Remove argv[0]
    exec_name = argv.pop(0)
    command = 'help'
    if len(argv) > 0:
        command = argv.pop(0)

        # Don't bother connecting for commands that don't need a device connection.
        if command not in ('list_devices', 'help'):
            if config.device is None or not exists(config.device):
                available_devices = list_devices(FLAGS.baudrate)
                if len(available_devices) > 1:
                    print('More than one device found. Please rerun the tool with the `list_devices` command and specify a target with --device.')
                    return 1
                if len(available_devices) == 0:
                    print('No busytag devices found.')
                    return 1
                bt = Device(available_devices[0], baudrate=FLAGS.baudrate)
            else:
                bt = Device(config.device, baudrate=FLAGS.baudrate)

    match command:
        case 'info':
            print(f'Device name:      {bt.name}')
            print(f'Device ID:        {bt.device_id}')
            print(f'Firmware version: {bt.firmware_version}')
            print(f'Serial port:      {bt.port}')
            print(f'Storage capacity: {format_size(bt.capacity)}')
            print(f'Free storage:     {format_size(bt.get_free_storage())}')

        case 'list_devices':
            devices = list_devices(FLAGS.baudrate)
            if len(devices) == 0:
                print('No devices found')
            else:
                print('Available devices:')
                for device in devices:
                    print(f'  {device}')

        case 'list_pictures':
            print('Pictures in device:')
            for picture in bt.list_pictures():
                print(f'  {picture.name} ({format_size(picture.size)})')
            print(f'Available space: {format_size(bt.get_free_storage())}')

        case 'list_files':
            print('Files in device: ')
            for file in bt.list_files():
                print(
                    f'  {file.name} ({file.type.value} - {format_size(file.size)})')
            print(f'Available space: {format_size(bt.get_free_storage())}')

        case 'set_picture':
            bt.set_active_picture(pop_arg(argv, command, 'filename'))

        case 'get_picture':
            print(f'Current active picture: {bt.get_active_picture()}')

        case 'put':
            filename = expanduser(pop_arg(argv, command, 'filename'))
            with open(filename, 'rb') as fp:
                bt.upload_file(basename(filename), fp.read(),
                               ProgressBar(f'Uploading {basename(filename)}'))

        case 'get':
            filename = pop_arg(argv, command, 'filename')
            data = bt.read_file(filename, ProgressBar(f'Downloading {filename}'))
            with open(filename, 'wb') as fp:
                fp.write(data)

        case 'rm':
            filename = pop_arg(argv, command, 'filename')
            bt.delete_file(filename)

        case 'set_led_solid_color':
            color = pop_arg(argv, command, 'colour')
            try:
                led_config = LedConfig(LedPin.ALL, color)
            except ValueError as e:
                raise UsageError(str(e))
            bt.set_led_solid_color(led_config)

        case 'apply_led_preset':
            preset_name = pop_arg(argv, command, 'preset name')
            try:
                preset = config.get_led_preset(preset_name)
            except ValueError as e:
                raise UsageError(str(e))

            # Clear all LEDs first
            bt.set_led_solid_color(LedConfig(LedPin.ALL, '000000'))
            for e in preset:
                bt.set_led_solid_color(e)

        case 'get_brightness':
            print(f'Brightness: {bt.get_display_brightness()}')

        case 'set_brightness':
            value = pop_arg(argv, command, 'brightness')
            try:
                brightness = int(value)
            except ValueError:
                raise UsageError(f'Brightness must be an integer, got {value!r}')
            if not 0 < brightness <= 100:
                raise UsageError('Brightness must be between 1 and 100')
            bt.set_display_brightness(brightness)

        case 'help':
            print(f'\n\tUSAGE: {exec_name} [flags] <command> [<args>]\n')
            print('Available commands:')
            print('  help: Prints this message')
            print('  list_devices: Lists available devices')
            print('  info: Displays device information')
            print('  list_pictures: Lists pictures in device')
            print('  list_files: Lists files in device')
            print('  get_picture: Gets the filename of the picture being shown')
            print(
                '  set_picture <filename>: Sets the picture shown in the device')
            print('  put <filename>: Uploads <filename>')
            print(
                '  get <filename>: Copies <filename> from the device to the working directory')
            print('  rm <filename>: Deletes <filename>')
            print(
                '  set_led_solid_color <6 hex RGB colour>: Sets the LEDs colour')
            print(
                '  apply_led_preset <preset name>: Sets the LEDs colour according to a preset')
            print('  get_brightness: Gets current display brightness')
            print(
                '  set_brightness <brightness>: Sets current display brightness (int between 1 and 100, inclusive)')
            print(f'\nFor flag documentation, run {exec_name} --help')

        case _:
            print(
                f'Unknown command `{command}`. Please use the `help` to list available commands')
            return 1

    return 0


def run_main():
    app.run(main)


if __name__ == '__main__':
    run_main()
