try:
    import usocket as socket
except ImportError:
    import socket
import struct

# ── exceptions ────────────────────────────────────────────────────────────────


class MCProtocolError(Exception):
    """PLC returned a non-zero end code."""
    def __init__(self, end_code):
        self.end_code = end_code
        super().__init__('MC error 0x{:04X}'.format(end_code))


class MCProtocolConnectionError(OSError):
    """Network-level communication failure."""
    pass


# ── constants ─────────────────────────────────────────────────────────────────

# Binary device codes (iQ-R / Q series)
_BIN_CODE = {
    'D': 0xA8, 'W': 0xB4, 'R': 0xAF, 'ZR': 0xB0,
    'X': 0x9C, 'Y': 0x9D, 'M': 0x90, 'L': 0x92,
    'B': 0xA0, 'F': 0x93, 'SB': 0xA1, 'SW': 0xB5,
    'TN': 0xC2, 'CN': 0xC5, 'Z': 0xCC,
}

# ASCII device number is decimal for word devices, hex for bit devices
_WORD_DEVS = frozenset({'D', 'W', 'R', 'ZR', 'TN', 'CN', 'Z', 'SW'})

_CMD_READ  = 0x0401
_CMD_WRITE = 0x1401
_WORD      = 0x0000
_BIT       = 0x0001

_HDR_BIN = b'\x50\x00\x00\xFF\xFF\x03\x00'
_HDR_ASC = '500000FF03FF00'


class MCProtocol3E:
    """3E frame MC protocol client (TCP, binary or ASCII mode)."""

    def __init__(self, host, port=1025, mode='binary', timeout=5.0, timer=0x0010):
        if mode not in ('binary', 'ascii'):
            raise ValueError("mode must be 'binary' or 'ascii'")
        self.host    = host
        self.port    = port
        self.mode    = mode
        self.timeout = timeout
        self.timer   = timer   # monitoring timer (units of 250 ms)
        self._sock   = None

    # ── connection ────────────────────────────────────────────────

    def connect(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(self.timeout)
        s.connect((self.host, self.port))
        self._sock = s

    def close(self):
        if self._sock:
            self._sock.close()
            self._sock = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *_):
        self.close()

    # ── send / recv helpers ───────────────────────────────────────

    def _send(self, data):
        if self._sock is None:
            raise MCProtocolConnectionError('not connected')
        total = 0
        while total < len(data):
            n = self._sock.send(data[total:])
            if not n:
                raise MCProtocolConnectionError('socket closed during send')
            total += n

    def _recv_n(self, n):
        if self._sock is None:
            raise MCProtocolConnectionError('not connected')
        buf = bytearray(n)
        pos = 0
        while pos < n:
            chunk = self._sock.recv(n - pos)
            if not chunk:
                raise MCProtocolConnectionError(
                    'connection closed after {} of {} bytes'.format(pos, n))
            got = min(len(chunk), n - pos)
            buf[pos:pos + got] = chunk[:got]
            pos += got
        return bytes(buf)

    # ── frame build / send ────────────────────────────────────────

    def _frame_bin(self, cmd, subcmd, body):
        payload = struct.pack('<HHH', self.timer, cmd, subcmd) + body
        return _HDR_BIN + struct.pack('<H', len(payload)) + payload

    def _frame_asc(self, cmd, subcmd, body):
        inner = '{:04X}{:04X}{:04X}'.format(self.timer, cmd, subcmd) + body
        return _HDR_ASC + '{:04X}'.format(len(inner)) + inner

    def _xfer_bin(self, frame):
        self._send(frame)
        hdr = self._recv_n(9)
        return hdr + self._recv_n(struct.unpack_from('<H', hdr, 7)[0])

    def _xfer_asc(self, frame):
        self._send(frame.encode())
        hdr = self._recv_n(18).decode()
        return hdr + self._recv_n(int(hdr[14:18], 16)).decode()

    # ── response check ────────────────────────────────────────────

    def _chk_bin(self, data):
        if len(data) < 11:
            raise MCProtocolConnectionError(
                'short response ({} bytes)'.format(len(data)))
        ec = struct.unpack_from('<H', data, 9)[0]
        if ec:
            raise MCProtocolError(ec)
        return data[11:]

    def _chk_asc(self, data):
        if len(data) < 22:
            raise MCProtocolConnectionError(
                'short response ({} chars)'.format(len(data)))
        ec = int(data[18:22], 16)
        if ec:
            raise MCProtocolError(ec)
        return data[22:]

    # ── device address encoding ───────────────────────────────────

    def _addr_bin(self, dev, addr):
        buf = bytearray(4)
        struct.pack_into('<I', buf, 0, addr)
        buf[3] = _BIN_CODE[dev]
        return bytes(buf)

    def _addr_asc(self, dev, addr):
        num = '{:06d}'.format(addr) if dev in _WORD_DEVS else '{:06X}'.format(addr)
        return dev.ljust(2) + num

    # ── input validation ──────────────────────────────────────────

    def _validate(self, device, start, count):
        dev = device.upper()
        if dev not in _BIN_CODE:
            raise ValueError("unsupported device '{}' (available: {})".format(
                device, ', '.join(sorted(_BIN_CODE))))
        if start < 0:
            raise ValueError('start must be >= 0, got {}'.format(start))
        if count <= 0:
            raise ValueError('count must be > 0, got {}'.format(count))
        return dev

    # ── public API ────────────────────────────────────────────────

    def read_words(self, device, start, count):
        """Read `count` word values from `device` starting at `start`."""
        dev = self._validate(device, start, count)
        if self.mode == 'binary':
            body = self._addr_bin(dev, start) + struct.pack('<H', count)
            raw = self._chk_bin(self._xfer_bin(self._frame_bin(_CMD_READ, _WORD, body)))
            if len(raw) < count * 2:
                raise MCProtocolConnectionError(
                    'short payload: expected {} bytes, got {}'.format(count * 2, len(raw)))
            return [struct.unpack_from('<H', raw, i * 2)[0] for i in range(count)]
        body = self._addr_asc(dev, start) + '{:04X}'.format(count)
        raw = self._chk_asc(self._xfer_asc(self._frame_asc(_CMD_READ, _WORD, body)))
        if len(raw) < count * 4:
            raise MCProtocolConnectionError(
                'short payload: expected {} chars, got {}'.format(count * 4, len(raw)))
        return [int(raw[i*4:(i+1)*4], 16) for i in range(count)]

    def write_words(self, device, start, values):
        """Write word `values` list to `device` starting at `start`."""
        dev = self._validate(device, start, len(values))
        if self.mode == 'binary':
            body = self._addr_bin(dev, start) + struct.pack('<H', len(values))
            wbuf = bytearray(len(values) * 2)
            for i, v in enumerate(values):
                struct.pack_into('<H', wbuf, i * 2, v)
            self._chk_bin(self._xfer_bin(self._frame_bin(_CMD_WRITE, _WORD, body + bytes(wbuf))))
            return
        body = self._addr_asc(dev, start) + '{:04X}'.format(len(values))
        body += ''.join('{:04X}'.format(v) for v in values)
        self._chk_asc(self._xfer_asc(self._frame_asc(_CMD_WRITE, _WORD, body)))

    def read_bits(self, device, start, count):
        """Read `count` bit values (0/1) from `device` starting at `start`."""
        dev = self._validate(device, start, count)
        if self.mode == 'binary':
            body = self._addr_bin(dev, start) + struct.pack('<H', count)
            raw = self._chk_bin(self._xfer_bin(self._frame_bin(_CMD_READ, _BIT, body)))
            expected = (count + 1) // 2
            if len(raw) < expected:
                raise MCProtocolConnectionError(
                    'short payload: expected {} bytes, got {}'.format(expected, len(raw)))
            bits = []
            for i in range(count):
                b = raw[i // 2]
                bits.append((b if i % 2 == 0 else b >> 4) & 0x01)
            return bits
        body = self._addr_asc(dev, start) + '{:04X}'.format(count)
        raw = self._chk_asc(self._xfer_asc(self._frame_asc(_CMD_READ, _BIT, body)))
        if len(raw) < count:
            raise MCProtocolConnectionError(
                'short payload: expected {} chars, got {}'.format(count, len(raw)))
        return [int(raw[i]) & 0x01 for i in range(count)]

    def write_bits(self, device, start, values):
        """Write bit `values` list (0/1) to `device` starting at `start`."""
        dev = self._validate(device, start, len(values))
        if self.mode == 'binary':
            body = self._addr_bin(dev, start) + struct.pack('<H', len(values))
            buf  = bytearray((len(values) + 1) // 2)
            for i, v in enumerate(values):
                buf[i // 2] |= (v & 0x01) << (0 if i % 2 == 0 else 4)
            self._chk_bin(self._xfer_bin(self._frame_bin(_CMD_WRITE, _BIT, body + bytes(buf))))
            return
        body = self._addr_asc(dev, start) + '{:04X}'.format(len(values))
        body += ''.join(str(v & 1) for v in values)
        self._chk_asc(self._xfer_asc(self._frame_asc(_CMD_WRITE, _BIT, body)))
