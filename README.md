# busytag_tool

Python library and CLI to interact with [Busy Tag](https://www.busy-tag.com/) devices using
the [USB CDC interface]( https://luxafor.helpscoutdocs.com/article/47-busy-tag-usb-cdc-command-reference-guide).

## Installation

```shell
$ pip install busytag
```

## CLI usage

The first time the tool is used, you should pass the device path through
the flag `--device=/dev/whatever`. This will be saved in `~/.busytag.toml`
and will be used in subsequent runs where `--device` is not passed.

```shell
$ busytag-tool 
Available commands:
  help: Prints this message
  info: Displays device information
  list_pictures: Lists pictures in device
  list_files: Lists files in device
  get_picture: Gets the filename of the picture being shown
  set_picture <filename>: Sets the picture shown in the device
  put <filename>: Uploads <filename>
  get <filename>: Copies <filename> from the device to the working directory
  rm <filename>: Deletes <filename>
  set_led_solid_color <6 hex RGB colour>: Sets the LEDs colour
  get_brightness: Gets current display brightness
  set_brightness <brightness>: Sets current display brightness (int between 1 and 100, inclusive
```

## API usage

```python
from busytag import Device

bt = Device('/dev/fooBar')
bt.set_active_picture('coding.gif')
```