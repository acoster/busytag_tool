import pytest
from absl import logging

from busytag import device as device_module
from busytag.busytag_types import LedConfig, LedPatternEntry, LedPin
from busytag.device import Device, generate_chunks

INFO_RESPONSES = {
    b'AT+GTSS': b'+TSS:1000000',
    b'AT+GID': b'+ID:ABC123',
    b'AT+GFV': b'+FV:2.0',
    b'AT+GLHA': b'+LHA:http://busytag-abc.local',
    b'AT+GMN': b'+MN:Luxafor',
    b'AT+GDN': b'+DN:busytag-abc',
}


class FakeSerial:
    """Minimal stand-in for serial.Serial that emulates the Busy Tag protocol."""

    def __init__(self, files=None):
        self.files = dict(files or {})
        self.buffer = b''
        self.pending_upload = None  # (filename, size, received bytes)
        self.is_open = True

    def close(self):
        self.is_open = False

    def _queue(self, data: bytes):
        self.buffer += data

    def write(self, data: bytes):
        if self.pending_upload is not None:
            name, size, received = self.pending_upload
            received += data
            if len(received) >= size:
                self.files[name] = received
                self.pending_upload = None
                self._queue(b'\r\nOK\r\n')
            else:
                self.pending_upload = (name, size, received)
            return

        command = data.strip()
        if command in INFO_RESPONSES:
            self._queue(INFO_RESPONSES[command] + b'\r\n')
        elif command.startswith(b'AT+UF='):
            name, size = command.removeprefix(b'AT+UF=').decode().split(',')
            self.pending_upload = (name, int(size), b'')
            self._queue(b'>\r\n')
        elif command.startswith(b'AT+GF='):
            name = command.removeprefix(b'AT+GF=').decode()
            contents = self.files[name]
            self._queue(f'+GF:{name},{len(contents)}\r\n'.encode())
            self._queue(b'\r\n' + contents + b'\r\nOK\r\n')
        else:
            raise AssertionError(f'Unexpected command {command!r}')

    def readline(self) -> bytes:
        idx = self.buffer.index(b'\n') + 1
        line, self.buffer = self.buffer[:idx], self.buffer[idx:]
        return line

    def read(self, n: int) -> bytes:
        data, self.buffer = self.buffer[:n], self.buffer[n:]
        return data


@pytest.mark.parametrize('n', [0, 1, 999, 1000, 1001, 2000, 2500, 10_000])
def test_generate_chunks_covers_all_bytes(n):
    chunks = list(generate_chunks(n))
    assert sum(chunks) == n
    assert all(0 < c <= 1000 for c in chunks)


def test_device_reads_info():
    bt = Device(connection=FakeSerial())
    assert bt.capacity == 1_000_000
    assert bt.device_id == 'ABC123'
    assert bt.hostname == 'busytag-abc.local'
    assert bt.port is None


def test_device_requires_port_or_connection():
    with pytest.raises(ValueError):
        Device()


@pytest.mark.parametrize('size', [10, 992, 1000, 2000, 2992, 3500])
def test_upload_and_download_roundtrip(size):
    conn = FakeSerial()
    bt = Device(connection=conn)
    data = bytes(i % 251 for i in range(size))

    bt.upload_file('pic.png', data)
    assert conn.files['pic.png'] == data
    assert bt.read_file('pic.png') == data


def test_led_config_normalizes_lowercase_color():
    assert LedConfig(LedPin.ALL, 'ff00aa').color == 'FF00AA'


@pytest.mark.parametrize('color', ['FF00', 'GG0000', 'FF00000', ''])
def test_led_config_rejects_invalid_color(color):
    with pytest.raises(ValueError):
        LedConfig(LedPin.ALL, color)


def test_led_pattern_entry_validation():
    assert str(LedPatternEntry(LedPin.PIN_0, 'abcdef', 1, 2)) == '1,ABCDEF,1,2'
    with pytest.raises(ValueError):
        LedPatternEntry(LedPin.PIN_0, 'ABCDEF', -1, 0)


def test_close_closes_connection():
    conn = FakeSerial()
    bt = Device(connection=conn)
    bt.close()
    assert not conn.is_open
    bt.close()  # Closing twice is harmless.


def test_context_manager_closes_connection():
    conn = FakeSerial()
    with Device(connection=conn) as bt:
        assert bt.device_id == 'ABC123'
        assert conn.is_open
    assert not conn.is_open


def test_init_closes_port_it_opened_on_failure(monkeypatch):
    class BrokenSerial(FakeSerial):
        def write(self, data):
            raise OSError('device went away')

    opened = []

    def fake_serial(port, baudrate):
        conn = BrokenSerial()
        opened.append(conn)
        return conn

    monkeypatch.setattr(device_module.serial, 'Serial', fake_serial)
    with pytest.raises(OSError):
        Device('/dev/fake')
    assert not opened[0].is_open


class FakePort:
    def __init__(self, device, product='BUSY TAG'):
        self.device = device
        self.product = product


def test_list_devices_logs_errors(monkeypatch):
    monkeypatch.setattr(device_module, 'comports',
                        lambda: [FakePort('/dev/locked'), FakePort('/dev/other', 'Other')])

    def failing_serial(*args, **kwargs):
        raise PermissionError('Permission denied')

    warnings = []
    monkeypatch.setattr(device_module.serial, 'Serial', failing_serial)
    monkeypatch.setattr(logging, 'warning', lambda msg, *a: warnings.append(msg % a if a else msg))

    assert device_module.list_devices(115200) == []
    assert len(warnings) == 1
    assert '/dev/locked' in warnings[0] and 'Permission denied' in warnings[0]
