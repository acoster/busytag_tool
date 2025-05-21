# busytag_tool
[![PyPI version](https://img.shields.io/pypi/v/busytag)](https://pypi.org/project/busytag/)
![License](https://img.shields.io/pypi/l/busytag)

Python library and CLI to interact with [Busy Tag](https://www.busy-tag.com/) devices using
the [USB CDC interface]( https://luxafor.helpscoutdocs.com/article/47-busy-tag-usb-cdc-command-reference-guide).

## Installation

```shell
$ pip install busytag
```

## CLI usage

The first time the tool is used, you should pass the device path through the flag `--device=/dev/whatever`. This
will be saved in `~/.busytag.toml` and will be used in later runs where `--device` is not passed. If you don't the port
for your device, you can run `busytag-tool list_devices` to find it.

```shell
$ busytag-tool

	USAGE: busytag-tool [flags] <command> [<args>]

Available commands:
  help: Prints this message
  list_devices: Lists available devices
  info: Displays device information
  list_pictures: Lists pictures in device
  list_files: Lists files in device
  get_picture: Gets the filename of the picture being shown
  set_picture <filename>: Sets the picture shown in the device
  put <filename>: Uploads <filename>
  get <filename>: Copies <filename> from the device to the working directory
  rm <filename>: Deletes <filename>
  set_led_solid_color <6 hex RGB colour>: Sets the LEDs colour
  apply_led_preset <preset name>: Sets the LEDs colour according to a preset
  get_brightness: Gets current display brightness
  set_brightness <brightness>: Sets current display brightness (int between 1 and 100, inclusive

$ busytag-tool set_picture coding.png
```

### Config

A config file with the device port is created at `~/.busytag.toml`. You can also add "led preset" entries there,
which can then be used with the `apply_led_preset` to change the device's LED colours. For example, here are two
entries, one that applies the same colour to all LEDs, and another that alternates colours:

```toml
[[led_presets.red]]
pins = 127
color = 'FF0000'

[[led_presets.rb]]
pins = 85
color = 'FF0000'

[[led_presets.rb]]
pins = 42
color = '0000FF'
```

The BusyTag device has seven LEDs (with the first one, 0, at the bottom left of the device), identified in this tool by
powers of two. The `pins` entry in the config is the sum of which pins we want to apply the colour (so `127` applies
to all, while `85` applies to pins 0, 2, 4 and 6).

## API usage

```python
from busytag import Device, LedConfig, LedPin

bt = Device('/dev/fooBar')
bt.set_active_picture('coding.gif')
bt.set_led_solid_color(LedConfig(LedPin.ALL, 'FF0000'))
```
