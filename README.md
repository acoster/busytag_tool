# busytag_tool

Python library (and soon CLI) to interact with [Busy Tag](https://www.busy-tag.com/) devices via USB,
using its [USB CDC interface]( https://luxafor.helpscoutdocs.com/article/47-busy-tag-usb-cdc-command-reference-guide).

## Basic usage

```python
from busytag import Device, LedConfig, LedPin

bt = Device('/dev/tty.usbmodemFOO')
bt.set_active_picture('coding.gif')
bt.set_led_solid_color(LedConfig(LedPin.ALL, 'FF4D00'))
```