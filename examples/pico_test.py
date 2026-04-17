"""
Pico 2 W — hardware communication test against mock_plc.py (running on PC).

Setup:
  1. Run mock_plc.py on PC
  2. Edit SSID / PASSWORD / PC_IP below
  3. Copy mcprotocol.py and this file to Pico 2 W
  4. Run this file (e.g. via Thonny or mpremote run pico_test.py)
"""
import network
import time
from mcprotocol import MCProtocol3E

# ── config ────────────────────────────────────────────────────────────────────

SSID     = 'your-ssid'
PASSWORD = 'your-password'
PC_IP    = '192.168.x.x'   # IP address of the PC running mock_plc.py
PORT     = 1025

# ── WiFi connect ──────────────────────────────────────────────────────────────

def wifi_connect():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(SSID, PASSWORD)
    print('Connecting to WiFi', end='')
    for _ in range(20):
        if wlan.isconnected():
            break
        time.sleep(0.5)
        print('.', end='')
    if not wlan.isconnected():
        raise OSError('WiFi connection failed')
    print(' OK')
    print('IP:', wlan.ifconfig()[0])


# ── tests ─────────────────────────────────────────────────────────────────────

def run_tests(plc):
    ok = 0
    ng = 0

    def check(label, actual, expected):
        nonlocal ok, ng
        if actual == expected:
            print('  PASS  {}'.format(label))
            ok += 1
        else:
            print('  FAIL  {}  got={} expected={}'.format(label, actual, expected))
            ng += 1

    # ── word read ─────────────────────────────────────────────────────────────
    print('[read_words D0+3]')
    vals = plc.read_words('D', 0, 3)
    check('D0=100', vals[0], 100)
    check('D1=200', vals[1], 200)
    check('D2=300', vals[2], 300)

    # ── word write → read back ────────────────────────────────────────────────
    print('[write_words D10+2 then read back]')
    plc.write_words('D', 10, [0x1234, 0x5678])
    vals = plc.read_words('D', 10, 2)
    check('D10=0x1234', vals[0], 0x1234)
    check('D11=0x5678', vals[1], 0x5678)

    # ── bit read ──────────────────────────────────────────────────────────────
    print('[read_bits X0+3]')
    bits = plc.read_bits('X', 0, 3)
    check('X0=1', bits[0], 1)
    check('X1=0', bits[1], 0)
    check('X2=1', bits[2], 1)

    # ── bit write → read back ─────────────────────────────────────────────────
    print('[write_bits M10+3 then read back]')
    plc.write_bits('M', 10, [1, 0, 1])
    bits = plc.read_bits('M', 10, 3)
    check('M10=1', bits[0], 1)
    check('M11=0', bits[1], 0)
    check('M12=1', bits[2], 1)

    print()
    print('Result: {}/{} passed'.format(ok, ok + ng))


# ── main ──────────────────────────────────────────────────────────────────────

wifi_connect()

with MCProtocol3E(PC_IP, port=PORT) as plc:
    print('Connected to mock PLC at {}:{}\n'.format(PC_IP, PORT))
    run_tests(plc)
