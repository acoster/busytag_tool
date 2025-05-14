from dataclasses import dataclass
from enum import Enum
from typing import Sequence, Optional

import logging
import serial

__all__ = ['Device', 'FileEntry', 'FileEntryType', 'WifiConfig']
logger = logging.getLogger(__name__)

class FileEntryType(Enum):
    FILE = 'file'
    DIRECTORY = 'dir'

@dataclass
class FileEntry:
    """File stored in the Busy Tag device."""
    name: str
    size: int
    type: FileEntryType = FileEntryType.FILE


@dataclass
class WifiConfig:
    """Wifi configuration."""
    ssid: str
    password: str


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

class Device(object):
    """Class to interact with Busy-Tag devices through a serial connection.

    The protocol to communicate with the Busy-Tag device is documented at
    https://luxafor.helpscoutdocs.com/article/47-busy-tag-usb-cdc-command-reference-guide.
    """

    def __init__(self, port_path: Optional[str] = None, connection : Optional[serial.Serial] = None):
        assert not (port_path is None and connection is None)
        if port_path is not None:
            self._port = port_path
            logger.info(f'Connecting to serial port {port_path}')
            self.conn = serial.Serial(port_path, 115200)
        else:
            self._port = None
            self.conn = connection

        self.__capacity = int(self.__exec_gquery('TSS'))
        self.__device_id = self.__exec_gquery('ID')
        self.__firmware_version = self.__exec_gquery('FV')
        self.__manufacturer = self.__exec_gquery('MN')
        self.__name = self.__exec_gquery('DN')

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
        """Reads a file stored on the device."""
        logger.info(f'Reading file {filename}')
        self.__send_command('AT+GF=%s' % (filename,))

        # First part of response: +GF:<filename>,<size in bytes>\r\n
        response = self.__read_response('+GF:')
        if b','  not in response:
            raise IOError('Malformed response to command AT+GF=%s' % (response,))

        read_size = int(response.split(b',')[1]) + 8
        logger.debug(f'Reading {read_size} bytes from device')
        response = self.conn.read(read_size)
        assert response[-6:] == b'\r\nOK\r\n'
        return response[2:-6]

    def upload_file(self, filename:str, data:bytes):
        """Writes a file to the device."""
        self.__send_command('AT+UF=%s,%d' % (filename, len(data)))
        self.__readline()
        logger.debug('Writing %d bytes to device', len(data))
        self.conn.write(data)
        terminator = self.conn.read(6)
        assert terminator == b'\r\nOK\r\n'

    def delete_file(self, filename: str):
        """Deletes a file from the device."""
        self.__send_command('AT+DF=%s' % (filename,))
        self.__read_response('+DF:')
        self.__read_response('OK')

    def set_active_picture(self, filename: str):
        """Set the picture that will be shown on the display."""
        self.__send_command('AT+SP=%s' % (filename,))
        self.__read_response('OK')

    def get_active_picture(self) -> str:
        """Gets the file name of the picture being displayed."""
        return self.__exec_query('SP')

    def get_free_storage(self) -> int:
        return int(self.__exec_gquery('FSS'))

    def get_display_brightness(self) -> int:
        return int(self.__exec_query('DB'))

    def set_display_brightness(self, brightness: int):
        if brightness < 1 or brightness > 100:
            raise ValueError('Brightness must be between 1 and 100')
        self.__send_command('AT+DB=%d' % (brightness,))
        self.__read_response('OK')

    def get_wifi_config(self) -> WifiConfig:
        response = self.__exec_query('WC')
        if ',' not in response:
            raise IOError(f'Malformed response to command AT+WC: {response}')
        ssid, password = response.split(',', 1)
        return WifiConfig(ssid, password)

    def set_wifi_config(self, wifi_config: WifiConfig):
        self.__send_command('AT+WC=%s,%s' % (wifi_config.ssid, wifi_config.password))
        self.__read_response('OK')

    def reset_wifi_config(self):
        self.__send_command('AT+FRWCF')
        self.__read_response('OK')

    @property
    def capacity(self) -> int:
        return self.__capacity

    @property
    def device_id(self) -> str:
        return self.__device_id

    @property
    def firmware_version(self) -> str:
        return self.__firmware_version

    @property
    def manufacturer(self) -> str:
        return self.__manufacturer

    @property
    def name(self) -> str:
        return self.__name

    def __exec_gquery(self, attribute: str) -> str:
        """Sends an `AT+G<attribute>` query, and returns the response without its prefix."""
        response_prefix = f'+{attribute}:'
        self.__send_command(f'AT+G{attribute}')
        return self.__read_response(response_prefix).decode().removeprefix(response_prefix)

    def __exec_query(self, attribute: str) -> str:
        """Sends an AT+<attribute>? query, and returns the response without its prefix."""
        response_prefix = f'+{attribute}:'
        self.__send_command(f'AT+{attribute}?')
        return self.__read_response(response_prefix).decode().removeprefix(response_prefix)

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
            raise build_exception(result)
        return result.strip()
