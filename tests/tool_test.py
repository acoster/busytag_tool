import pytest
from absl import flags

from busytag import tool


@pytest.fixture(autouse=True)
def parse_flags(tmp_path):
    flags.FLAGS(['busytag-tool'])
    flags.FLAGS.config_file = str(tmp_path / 'config.toml')
    yield
    flags.FLAGS.unparse_flags()


def test_pop_arg_missing_raises_usage_error():
    with pytest.raises(tool.UsageError):
        tool.pop_arg([], 'rm', 'filename')


def test_help_returns_zero(capsys):
    assert tool.main(['busytag-tool', 'help']) == 0
    assert 'set_brightness' in capsys.readouterr().out


def test_unknown_command_returns_one(monkeypatch):
    # Avoid touching real hardware.
    monkeypatch.setattr(tool, 'list_devices', lambda baudrate: [])
    assert tool.main(['busytag-tool', 'bogus']) == 1
