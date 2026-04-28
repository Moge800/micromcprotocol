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
| SB | 0xA1 | Bit |
| SW | 0xB5 | Word |
| TN | 0xC2 | Word |
| CN | 0xC5 | Word |
| Z | 0xCC | Word |

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

### `MCProtocol3E(host, port=1025, mode='binary', timeout=5.0, timer=0x0010)`

| Parameter | Default | Description |
|-----------|---------|-------------|
| `host` | — | PLC IP address |
| `port` | `1025` | TCP port |
| `mode` | `'binary'` | `'binary'` or `'ascii'` |
| `timeout` | `5.0` | Socket timeout in seconds |
| `timer` | `0x0010` | Monitoring timer (units of 250 ms) |

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

Raises `MCProtocolError` (with `end_code` attribute) on PLC errors, and `MCProtocolConnectionError` (subclass of `OSError`) on network failures.

## Memory Usage (MicroPython)

This library allocates only what each operation needs — no large static buffers.
Typical heap usage per call is well under 1 KB, making it suitable for ESP32-class
devices (e.g. M5Stamp) with ~150–250 KB of available heap after boot.

**Recommendations for constrained devices:**

| Guideline | Detail |
|-----------|--------|
| Prefer binary mode | ASCII mode builds intermediate strings and uses more heap |
| Keep batch size moderate | Reading 500+ words at once produces a large result list; prefer smaller batches |
| Typical safe range | 10–100 words / 8–256 bits per request is well within limits |

## Scope

**Supported:**
- 3E frame over TCP
- Binary and ASCII encoding
- Batch read / write for word and bit devices

**Not supported (by design):**
- UDP transport
- Random read / write (multi-device mixed access)
- Monitor mode
- Extended frames (4E, etc.)
- Remote control commands (Run / Stop / Reset)

## Notes

- In binary bit read/write, two bit values are packed per byte — even-index in the high nibble, odd-index in the low nibble.
- ASCII mode encodes word device addresses as decimal, bit device addresses as hex — matching Mitsubishi PLC specification.
- The maximum points per request depends on the PLC model (typically 960 words / 7168 bits for batch read).

## Running Tests

```bash
python -m unittest test_mcprotocol -v
```

## License

MIT
