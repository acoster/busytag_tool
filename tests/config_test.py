import os

import pytest
import tomlkit
from busytag.config import ToolConfig
from busytag.types import LedConfig, LedPin


@pytest.fixture
def testdata_path():
    def _testdata_path(name):
        return os.path.join(os.path.dirname(__file__), 'testdata',
                            f"{name}.toml")

    return _testdata_path


def test_loads_config_with_device(testdata_path):
    config = ToolConfig(testdata_path('config-with-device'))
    assert config.device == '/dev/tty.usbmodem'


def test_loads_config_with_led_preset(testdata_path):
    config = ToolConfig(testdata_path('config-with-led-patterns'))
    expected_rb_pattern = {
        LedConfig(
            pins=LedPin.PIN_0 | LedPin.PIN_2 | LedPin.PIN_4 | LedPin.PIN_6,
            color='FF0000'),
        LedConfig(
            pins=LedPin.PIN_1 | LedPin.PIN_3 | LedPin.PIN_5,
            color='0000FF'
        )
    }

    diff = set(config.get_led_preset('rb')) ^ expected_rb_pattern
    assert not diff



def test_writes_config(tmp_path):
    p = tmp_path / 'config_with_device.toml'
    config = ToolConfig(str(p))

    assert config.device is None
    config.device = '/dev/tty.somedevice'
    config.write_to_file()

    c = tomlkit.loads(p.read_text())
    assert c['device'] == '/dev/tty.somedevice'
