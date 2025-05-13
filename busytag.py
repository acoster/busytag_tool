from unittest import case

import serial
from dataclasses import dataclass
from enum import Enum

class FileEntryType(Enum):
    FILE = 'file'
    DIRECTORY = 'dir'

def build_exception(error_response: bytes) -> Exception:
    if not error_response.startswith(b'ERROR:'):
        return Exception('Unexpected error response %s' % (error_response.decode(),))

    parts = error_response.decode().strip().split(':')
    if len(parts) != 2:
        return Exception('Unexpected error response %s' % (error_response.decode(),))

    match parts[1]:
        case '-1':
            return Exception('Unexpected error response %s' % (error_response.decode(),))
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
            return Exception('Unexpected error response %s' % (error_response.decode(),))


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
        self.__device_id = self.__read_response('+ID').decode().removeprefix('+ID:')

        self.__send_command('AT+GFV')
        self.__firmware_version = self.__read_response('+FV').decode().removeprefix('+FV:')

    def list_pictures(self):
        self.__send_command('AT+GPL')
        result = []
        while True:
            l = self.__read_line()
            if l.startswith(b'+evn'):
                continue

            if l.startswith(b'OK'):
                return result

            filename, size = l.decode().removeprefix('+PL:').split(',')
            result.append(FileEntry(filename, int(size)))

    def list_files(self):
        self.__send_command('AT+GFL')
        result = []
        while True:
            l = self.__read_line()
            if l.startswith(b'+evn'):
                continue

            if l.startswith(b'OK'):
                return result

            filename, entry_type, size = l.decode().removeprefix('+FL:').split(',')
            result.append(FileEntry(filename, int(size), FileEntryType(entry_type)))

    def read_file(self, filename: str) -> bytes:
        self.__send_command('AT+GF=%s' % (filename,))
        result = self.__read_line()
        if not result.startswith(b'+GF:'):
            raise IOError(result)
        self.__read_line()

        result = self.conn.read_until('\r\nOK\r\n')
        return result[:-6]

    def set_picture(self, filename: str):
        self.__send_command('AT+SP=%s' % (filename,))
        while True:
            response =  self.__read_line()
            if response.startswith(b'OK'):
                return True

    def get_free_storage(self) -> int:
        self.__send_command('AT+GTSS')
        return int(self.__read_response('+TSS').decode().removeprefix('+TSS:'))

    @property
    def name(self) -> str:
        return self.__name

    @property
    def device_id(self) -> str:
        return self.__device_id

    @property
    def firmware_version(self) -> str:
        return self.__firmware_version

    def __send_command(self, command: str):
        self.conn.write(command.encode() + b'\r\n')

    def __read_response(self, prefix: str) -> bytes:
        while True:
            response = self.__read_line()
            if response.startswith(prefix.encode()):
                return response

    def __read_line(self) -> bytes:
        result = self.conn.readline()
        if result.startswith(b'ERROR'):
            raise build_exception(result)
        return result.strip()

