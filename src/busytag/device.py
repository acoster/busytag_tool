# SPDX-License-Identifier: MIT

import logging
from typing import Sequence, Optional

from .types import *

import serial

__all__ = ['Device']
logger = logging.getLogger(__name__)


class Device(object):
    """Class to interact with Busy-Tag devices through a serial connection.

    The protocol to communicate with the Busy-Tag device is documented at
    https://luxafor.helpscoutdocs.com/article/47-busy-tag-usb-cdc-command-reference-guide.
    """

    def __init__(self, port_path: Optional[str] = None,
                 connection: Optional[serial.Serial] = None):
        assert not (port_path is None and connection is None)
        if port_path is not None:
            self._port = port_path
            logger.info(f'Connecting to serial port {port_path}')
            self.conn = serial.Serial(port_path, 115200)
        else:
            self._port = None
            self.conn = connection

        self.__capacity = int(self.__get_readonly_attribute('TSS'))
        self.__device_id = self.__get_readonly_attribute('ID')
        self.__firmware_version = self.__get_readonly_attribute('FV')
        self.__hostname = self.__get_readonly_attribute('LHA').removeprefix(
            'http://')
        self.__manufacturer = self.__get_readonly_attribute('MN')
        self.__name = self.__get_readonly_attribute('DN')

    def list_pictures(self) -> Sequence[FileEntry]:
        """Lists pictures that can be displayed on the screen."""
        self.__send_command('AT+GPL')
        result = []
        while True:
            l = self.__readline()
            # Unlikely, but event messages might arrive while we're listing
            # files. Silently consume them.
            if l.startswith(b'+evn'):
                continue

            if l.startswith(b'OK'):
                break

            filename, size = l.decode().removeprefix('+PL:').split(',')
            result.append(FileEntry(filename, int(size)))

        return result

    def list_files(self) -> Sequence[FileEntry]:
        """Lists all files stored on the device."""
        self.__send_command('AT+GFL')
        result = []
        while True:
            l = self.__readline()
            if l.startswith(b'+evn'):
                continue
            if l.startswith(b'OK'):
                break
            filename, entry_type, size = l.decode().removeprefix('+FL:').split(
                ',')
            result.append(
                FileEntry(filename, int(size), FileEntryType(entry_type)))

        return result

    def read_file(self, filename: str) -> bytes:
        """Reads a file from the device.

        :param filename: The filename of the file to read
        :return: a `bytes` object with the file contents
        """
        logger.info(f'Reading file {filename}')

        self.__send_command('AT+GF=%s' % (filename,))
        # First part of response: +GF:<filename>,<size in bytes>\r\n
        response = self.__read_response('+GF:')
        if b',' not in response:
            raise IOError(
                'Malformed response to command AT+GF=%s' % (response,))

        read_size = int(response.split(b',')[1]) + 8
        logger.debug(f'Reading {read_size} bytes from device')
        response = self.conn.read(read_size)
        assert response[-6:] == b'\r\nOK\r\n'
        return response[2:-6]

    def upload_file(self, filename: str, data: bytes):
        """Uploads a file to the device.

        :param filename: The filename of the file to upload
        :param data: The contents of the file to upload
        """
        logger.info(f'Uploading file {filename} ({len(data)} bytes)')

        self.__send_command('AT+UF=%s,%d' % (filename, len(data)))
        self.__readline()
        logger.debug('Writing %d bytes to device', len(data))
        self.conn.write(data)
        terminator = self.conn.read(6)
        assert terminator == b'\r\nOK\r\n'

    def delete_file(self, filename: str):
        """Deletes a file from the device.'

        :param filename: The filename of the file to delete
        """
        logger.info(f'Deleting file {filename}')
        self.__send_command('AT+DF=%s' % (filename,))
        self.__read_response('+DF:')
        self.__read_response('OK')

    def set_active_picture(self, filename: str):
        """Set the picture that will be shown on the display."""
        logger.info(f'Setting active picture {filename}')
        self.__set_attribute('SP', filename)

    def get_active_picture(self) -> str:
        """Gets the file name of the picture being displayed."""
        return self.__get_attribute('SP')

    def get_free_storage(self) -> int:
        return int(self.__get_readonly_attribute('FSS'))

    def get_display_brightness(self) -> int:
        return int(self.__get_attribute('DB'))

    def set_display_brightness(self, brightness: int):
        if brightness < 1 or brightness > 100:
            raise ValueError('Brightness must be between 1 and 100')
        self.__set_attribute('DB', f'{brightness}')

    def get_led_solid_color(self) -> LedConfig:
        pins, rgb = self.__get_attribute('SC').split(',')
        return LedConfig(LedPin(int(pins)), rgb)

    def set_led_solid_color(self, config: LedConfig):
        self.__set_attribute('SC', f'{int(config.pins)},{config.color}')

    def get_led_pattern(self) -> Sequence[LedPatternEntry]:
        result = []
        self.__send_command('AT+CP?')
        while True:
            entry = self.__readline().strip()
            if entry.startswith(b'ERROR'):
                logger.error('Received error response: %s', entry)
                raise self.build_exception(entry)
            if entry.startswith(b'+CP'):
                pins, rgb, speed, delay = entry.removeprefix(
                    b'+CP:').decode().split(',')
                result.append(
                    LedPatternEntry(LedPin(int(pins)), rgb, int(speed),
                                    int(delay)))
            elif entry.startswith(b'OK'):
                break

        return result

    def set_led_pattern(self, pattern: Sequence[LedPatternEntry]):
        assert 0 < len(pattern) <= 40
        self.__send_command(f'AT+CP={len(pattern)}')
        self.__read_response('>')
        for entry in pattern:
            self.__send_command(f'+CP:{entry}')
        self.__read_response('OK')

    def get_wifi_config(self) -> WifiConfig:
        response = self.__get_attribute('WC')
        if ',' not in response:
            raise IOError(f'Malformed response to command AT+WC: {response}')
        ssid, password = response.split(',', 1)
        return WifiConfig(ssid, password)

    def set_wifi_config(self, wifi_config: WifiConfig):
        logger.info(f'Setting Wifi SSID to {wifi_config.ssid}')
        self.__set_attribute('WC', f'{wifi_config.ssid},{wifi_config.password}')

    def reset_wifi_config(self):
        logger.info('Resetting wifi configuration')
        self.__send_command('AT+FRWCF')
        self.__read_response('OK')

    @property
    def capacity(self) -> int:
        return self.__capacity

    @property
    def device_id(self) -> str:
        return self.__device_id

    @property
    def hostname(self) -> str:
        return self.__hostname

    @property
    def firmware_version(self) -> str:
        return self.__firmware_version

    @property
    def manufacturer(self) -> str:
        return self.__manufacturer

    @property
    def name(self) -> str:
        return self.__name

    def __get_readonly_attribute(self, attribute: str) -> str:
        """Retrieves the value of a read-only attribute (e.g. device id)."""
        response_prefix = f'+{attribute}:'
        self.__send_command(f'AT+G{attribute}')
        return self.__read_response(response_prefix).decode().removeprefix(
            response_prefix)

    def __get_attribute(self, attribute: str) -> str:
        """Retrieves the value of a user-modifiable attribute (e.g. active picture)."""
        response_prefix = f'+{attribute}:'
        self.__send_command(f'AT+{attribute}?')
        return self.__read_response(response_prefix).decode().removeprefix(
            response_prefix)

    def __set_attribute(self, attribute: str, value: str):
        """Sets the value of a user-modifiable attribute (e.g. active picture)."""
        self.__send_command(f'AT+{attribute}={value}')
        self.__read_response('OK')

    def __send_command(self, command: str):
        encoded_command = command.encode() + b'\r\n'
        logger.debug('Sending command: %s', encoded_command)
        self.conn.write(encoded_command)

    def __read_response(self, prefix: str) -> bytes:
        logger.debug(f'Waiting for prefix: {prefix}')
        encoded_prefix = prefix.encode()
        while True:
            response = self.__readline()
            if response.startswith(encoded_prefix):
                return response

    def __readline(self) -> bytes:
        result = self.conn.readline()
        logger.debug('Read from device: %s', result)
        if result.startswith(b'ERROR'):
            logger.error('Received error response: %s', result)
            raise self.build_exception(result)
        return result.strip()

    @staticmethod
    def build_exception(error_response: bytes) -> Exception:
        """Converts an error response from Busy Tag to an Exception"""
        if not error_response.startswith(b'ERROR:'):
            return Exception(
                'Unexpected error response %s' % (error_response.decode(),))

        parts = error_response.decode().strip().split(':')
        if len(parts) != 2:
            return Exception(
                'Unexpected error response %s' % (error_response.decode(),))

        match parts[1]:
            case '-1':
                return Exception(
                    'Unexpected error response %s' % (error_response.decode(),))
            case '0':
                return Exception('Unknown error')
            case '1':
                return ValueError('Invalid command')
            case '2':
                return ValueError('Invalid argument')
            case '3':
                return FileNotFoundError('File not found')
            case '4':
                return ValueError('Invalid size')
            case _:
                return Exception(
                    'Unexpected error response %s' % (error_response.decode(),))