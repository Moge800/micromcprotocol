# micromcprotocol

> **⚠ Prototype / Experimental**
> This library is a work in progress. **Real hardware testing is planned but not yet done.**
> APIs may change without notice. Use in production at your own risk.

Lightweight MC Protocol (3E frame) client for MicroPython — designed for ESP32 and Raspberry Pi Pico W.

Inspired by [pymcprotocol](https://github.com/senrust/pymcprotocol).

## Features

- 3E frame over TCP
- Binary and ASCII mode (switchable)
- Batch read / write for word and bit devices
- Single file, zero dependencies (`socket` + `struct` only)
- MicroPython compatible (`usocket` auto-fallback)

## Supported Devices

| Device | Code | Type |
|--------|------|------|
| D | 0xA8 | Word |
| W | 0xB4 | Word |
| R | 0xAF | Word |
| ZR | 0xB0 | Word |
| X | 0x9C | Bit |
| Y | 0x9D | Bit |
| M | 0x90 | Bit |
| L | 0x92 | Bit |
| B | 0xA0 | Bit |
| F | 0x93 | Bit |
| TN | 0xC2 | Word |
| CN | 0xC5 | Word |

## Requirements

- MicroPython (ESP32 / Pico W) or CPython 3.x
- PLC with MC Protocol 3E frame enabled over TCP

## Installation

Copy `mcprotocol.py` to your device.

```bash
# Example using mpremote
mpremote cp mcprotocol.py :mcprotocol.py
```

## Usage

### Basic (binary mode)

```python
from mcprotocol import MCProtocol3E

with MCProtocol3E('192.168.1.10', port=1025) as plc:
    # Read D100–D109 (10 words)
    values = plc.read_words('D', 100, 10)
    print(values)  # [0, 0, 123, ...]

    # Write D200–D202
    plc.write_words('D', 200, [1, 2, 3])

    # Read M0–M7 (8 bits)
    bits = plc.read_bits('M', 0, 8)
    print(bits)  # [1, 0, 1, 0, ...]

    # Write Y0–Y2
    plc.write_bits('Y', 0, [1, 0, 1])
```

### ASCII mode

```python
plc = MCProtocol3E('192.168.1.10', port=1025, mode='ascii')
plc.connect()
values = plc.read_words('D', 0, 5)
plc.close()
```

### ESP32 with WiFi

```python
import network
from mcprotocol import MCProtocol3E

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect('SSID', 'PASSWORD')
while not wlan.isconnected():
    pass

with MCProtocol3E('192.168.1.10') as plc:
    print(plc.read_words('D', 0, 1))
```

## API

### `MCProtocol3E(host, port=1025, mode='binary', timeout=5.0)`

| Parameter | Default | Description |
|-----------|---------|-------------|
| `host` | — | PLC IP address |
| `port` | `1025` | TCP port |
| `mode` | `'binary'` | `'binary'` or `'ascii'` |
| `timeout` | `5.0` | Socket timeout in seconds |

### Methods

| Method | Description |
|--------|-------------|
| `connect()` | Open TCP connection |
| `close()` | Close TCP connection |
| `read_words(device, start, count)` | Read `count` words starting at `start` |
| `write_words(device, start, values)` | Write word list starting at `start` |
| `read_bits(device, start, count)` | Read `count` bits (returns list of 0/1) |
| `write_bits(device, start, values)` | Write bit list (0/1) starting at `start` |

Context manager (`with` statement) calls `connect()` / `close()` automatically.

Raises `RuntimeError` with the PLC end code on communication errors.

## Notes

- ASCII mode encodes word device addresses as decimal, bit device addresses as hex — matching Mitsubishi PLC specification.
- The maximum points per request depends on the PLC model (typically 960 words / 7168 bits for batch read).
- No remote control commands (Run / Stop / Reset) are included by design.

## Running Tests

```bash
python -m unittest test_mcprotocol -v
```

## License

MIT
