from dataclasses import dataclass
from enum import Enum
from typing import Sequence

import serial


class FileEntryType(Enum):
    FILE = 'file'
    DIRECTORY = 'dir'


def build_exception(error_response: bytes) -> Exception:
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


@dataclass
class FileEntry:
    """File in the busytag device"""
    name: str
    size: int
    type: FileEntryType = FileEntryType.FILE


class Device(object):
    def __init__(self, port: str):
        self._port = port
        self.conn = serial.Serial(port, 115200)

        self.__send_command('AT+GDN')
        self.__name = self.__read_response('+DN').decode().removeprefix('+DN:')

        self.__send_command('AT+GID')
        self.__device_id = self.__read_response('+ID').decode().removeprefix(
            '+ID:')

        self.__send_command('AT+GFV')
        self.__firmware_version = self.__read_response(
            '+FV').decode().removeprefix('+FV:')

        self.__send_command('AT+GTSS')
        self.__capacity = int(self.__read_response(
            '+TSS').decode().removeprefix('+TSS:'))

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
        self.__send_command('AT+GF=%s' % (filename,))

        # First part of response: +GF:<filename>,<size in bytes>\r\n
        response = self.__read_response('+GF:')
        if b','  not in response:
            raise IOError('Malformed response to command AT+GF=%s' % (response,))

        file_size = int(response.split(b',')[1])
        # \r\n between response and file
        self.__readline()
        response = self.conn.read(file_size)

        # After the file, terminate with \r\nOK\r\n
        terminator = self.conn.read(6)
        assert terminator == b'\r\nOK\r\n'
        return response

    def upload_file(self, filename:str, data:bytes):
        self.__send_command('AT+UF=%s,%d' % (filename, len(data)))
        self.__readline()
        self.conn.write(data)

        terminator = self.conn.read(6)
        assert terminator == b'\r\nOK\r\n'

    def delete_file(self, filename: str):
        self.__send_command('AT+DF=%s' % (filename,))
        self.__read_response('+DF:')
        self.__read_response('OK')

    def set_active_picture(self, filename: str):
        self.__send_command('AT+SP=%s' % (filename,))
        self.__read_response('OK')

    def get_active_picture(self) -> str:
        self.__send_command('AT+SP?')
        return self.__read_response('+SP').decode().removeprefix('+SP:')

    def get_free_storage(self) -> int:
        self.__send_command('AT+GFSS')
        return int(self.__read_response('+FSS').decode().removeprefix('+FSS:'))

    def get_display_brightness(self) -> int:
        self.__send_command('AT+DB?')
        return int(self.__read_response('+DB').decode().removeprefix('+DB:'))

    def set_display_brightness(self, brightness: int):
        if brightness < 1 or brightness > 100:
            raise ValueError('Brightness must be between 1 and 100')
        self.__send_command('AT+DB=%d' % (brightness,))
        self.__read_response('OK')

    @property
    def name(self) -> str:
        return self.__name

    @property
    def device_id(self) -> str:
        return self.__device_id

    @property
    def firmware_version(self) -> str:
        return self.__firmware_version

    @property
    def capacity(self) -> int:
        return self.__capacity

    def __send_command(self, command: str):
        self.conn.write(command.encode() + b'\r\n')

    def __read_response(self, prefix: str) -> bytes:
        encoded_prefix = prefix.encode()
        while True:
            response = self.__readline()
            if response.startswith(encoded_prefix):
                return response

    def __readline(self) -> bytes:
        result = self.conn.readline()
        if result.startswith(b'ERROR'):
            raise build_exception(result)
        return result.strip()
