"""
Mock PLC server — runs on PC, simulates a Mitsubishi PLC (3E frame binary, TCP).

Usage:
    python mock_plc.py              # listens on 0.0.0.0:1025
    python mock_plc.py 192.168.1.5  # bind to specific interface
"""
import socket
import struct
import sys

# ── simulated device memory ───────────────────────────────────────────────────
# key: (device_name, address)  value: int

_mem = {}

def _rw(dev, addr, default=0):
    return _mem.get((dev, addr), default)

def _ww(dev, addr, val):
    _mem[(dev, addr)] = val & 0xFFFF
    print('  [write] {}{}  = {}'.format(dev, addr, val & 0xFFFF))

def _rb(dev, addr):
    return _mem.get((dev, addr), 0) & 0x01

def _wb(dev, addr, val):
    _mem[(dev, addr)] = val & 0x01
    print('  [write] {}{} = {}'.format(dev, addr, val & 0x01))


def _preload():
    """Pre-load recognisable test values so reads return something useful."""
    for i in range(10):
        _mem[('D', i)] = (i + 1) * 100   # D0=100  D1=200 ... D9=1000
    for i in range(10):
        _mem[('W', i)] = 0xA000 + i       # W0=0xA000 W1=0xA001 ...
    _mem[('X', 0)] = 1
    _mem[('X', 1)] = 0
    _mem[('X', 2)] = 1
    _mem[('M', 0)] = 1
    _mem[('M', 1)] = 1
    _mem[('Y', 0)] = 0


# ── device code → name ────────────────────────────────────────────────────────

_DEV = {
    0xA8: 'D',  0xB4: 'W',  0xAF: 'R',  0xB0: 'ZR',
    0x9C: 'X',  0x9D: 'Y',  0x90: 'M',  0x92: 'L',
    0xA0: 'B',  0x93: 'F',  0xA1: 'SB', 0xB5: 'SW',
    0xC2: 'TN', 0xC5: 'CN', 0xCC: 'Z',
}

_CMD_READ  = 0x0401
_CMD_WRITE = 0x1401
_WORD      = 0x0000
_BIT       = 0x0001


# ── frame helpers ─────────────────────────────────────────────────────────────

def _response(data=b'', end_code=0):
    body = struct.pack('<H', end_code) + data
    return b'\xD0\x00\x00\xFF\xFF\x03\x00' + struct.pack('<H', len(body)) + body


def _handle(req):
    if len(req) < 21:
        return _response(end_code=0x4000)

    cmd    = struct.unpack_from('<H', req, 11)[0]
    subcmd = struct.unpack_from('<H', req, 13)[0]
    addr   = struct.unpack_from('<I', req[15:18] + b'\x00', 0)[0]
    dev    = _DEV.get(req[18], '?')
    count  = struct.unpack_from('<H', req, 19)[0]

    print('  CMD={:#06x} SUB={:#06x} DEV={} ADDR={} COUNT={}'.format(
        cmd, subcmd, dev, addr, count))

    if cmd == _CMD_READ:
        if subcmd == _WORD:
            data = b''.join(struct.pack('<H', _rw(dev, addr + i)) for i in range(count))
            vals = [_rw(dev, addr + i) for i in range(count)]
            print('  [read]  {}{}+{} = {}'.format(dev, addr, count, vals))
            return _response(data)
        else:  # BIT
            buf = bytearray((count + 1) // 2)
            vals = []
            for i in range(count):
                v = _rb(dev, addr + i)
                vals.append(v)
                buf[i // 2] |= v << (0 if i % 2 == 0 else 4)
            print('  [read]  {}{}+{} = {}'.format(dev, addr, count, vals))
            return _response(bytes(buf))

    elif cmd == _CMD_WRITE:
        if subcmd == _WORD:
            for i in range(count):
                val = struct.unpack_from('<H', req, 21 + i * 2)[0]
                _ww(dev, addr + i, val)
        else:  # BIT
            for i in range(count):
                b = req[21 + i // 2]
                _wb(dev, addr + i, (b if i % 2 == 0 else b >> 4) & 0x01)
        return _response()

    return _response(end_code=0x4000)


# ── recv helper (reliable read) ───────────────────────────────────────────────

def _recv_n(conn, n):
    buf = b''
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf


# ── server loop ───────────────────────────────────────────────────────────────

def serve(host='0.0.0.0', port=1025):
    _preload()
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((host, port))
    srv.listen(1)
    print('Mock PLC ready  {}:{}'.format(host, port))
    print('Pre-loaded: D0-D9=[100,200,...,1000]  W0-W9=[0xA000,...]  X0=1 X2=1 M0=1 M1=1')
    print()

    while True:
        conn, addr = srv.accept()
        print('>> connected from', addr)
        try:
            while True:
                hdr = _recv_n(conn, 9)
                if not hdr:
                    break
                data_len = struct.unpack_from('<H', hdr, 7)[0]
                body = _recv_n(conn, data_len)
                if body is None:
                    break
                resp = _handle(hdr + body)
                conn.sendall(resp)
        except Exception as e:
            print('error:', e)
        finally:
            conn.close()
            print('<< disconnected\n')


if __name__ == '__main__':
    host = sys.argv[1] if len(sys.argv) > 1 else '0.0.0.0'
    serve(host)
