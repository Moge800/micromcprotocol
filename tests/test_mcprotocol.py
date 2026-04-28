"""
Tests for MCProtocol3E.
All tests use a mock socket — no PLC required.
"""

import struct
import sys
import os
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from mcprotocol import MCProtocol3E, MCProtocolError, MCProtocolConnectionError


# ── helpers: build fake PLC responses ────────────────────────────────────────


def _bin_resp(end_code=0, data=b""):
    """Full binary 3E response frame."""
    body = struct.pack("<H", end_code) + data
    return b"\xd0\x00\x00\xff\xff\x03\x00" + struct.pack("<H", len(body)) + body


def _asc_resp(end_code=0, data=""):
    """Full ASCII 3E response frame (as bytes)."""
    body = "{:04X}{}".format(end_code, data)
    return ("D00000FF03FF00{:04X}".format(len(body)) + body).encode()


def _bin_side(end_code=0, data=b""):
    """recv side_effect for binary mode: [header(9 bytes), body]."""
    resp = _bin_resp(end_code, data)
    return [resp[:9], resp[9:]]


def _asc_side(end_code=0, data=""):
    """recv side_effect for ASCII mode: [header(18 bytes), body]."""
    resp = _asc_resp(end_code, data)
    return [resp[:18], resp[18:]]


def _plc(mode="binary"):
    """MCProtocol3E with a mocked socket (no real connection)."""
    p = MCProtocol3E("127.0.0.1", mode=mode)
    p._sock = MagicMock()
    p._sock.send.side_effect = lambda data: len(data)
    return p


def _sent(plc):
    """Return the bytes passed to the last sock.send() call."""
    return plc._sock.send.call_args[0][0]


# ── binary frame structure ────────────────────────────────────────────────────


class TestBinaryFrames(unittest.TestCase):

    def test_read_words_frame_exact(self):
        """read_words('D', 100, 3) must produce the exact 3E binary frame."""
        p = _plc()
        p._sock.recv.side_effect = _bin_side(data=b"\x00\x00" * 3)
        p.read_words("D", 100, 3)
        expected = (
            b"\x50\x00\x00\xff\xff\x03\x00"  # subheader + routing
            b"\x0c\x00"  # data length = 12
            b"\x10\x00"  # timer
            b"\x01\x04"  # CMD READ  0x0401 LE
            b"\x00\x00"  # subcmd WORD
            b"\x64\x00\x00"  # addr 100, 3 bytes LE
            b"\xa8"  # device D
            b"\x03\x00"  # point count 3
        )
        self.assertEqual(_sent(p), expected)

    def test_write_words_frame_exact(self):
        """write_words('D', 0, [0xABCD]) must include CMD WRITE and value LE."""
        p = _plc()
        p._sock.recv.side_effect = _bin_side()
        p.write_words("D", 0, [0xABCD])
        expected = (
            b"\x50\x00\x00\xff\xff\x03\x00"
            b"\x0e\x00"  # data length = 14
            b"\x10\x00"
            b"\x01\x14"  # CMD WRITE 0x1401 LE
            b"\x00\x00"
            b"\x00\x00\x00"  # addr 0
            b"\xa8"  # device D
            b"\x01\x00"  # count 1
            b"\xcd\xab"  # 0xABCD LE
        )
        self.assertEqual(_sent(p), expected)

    def test_read_bits_uses_bit_subcmd(self):
        """read_bits must set subcommand to BIT (0x0001)."""
        p = _plc()
        p._sock.recv.side_effect = _bin_side(data=b"\x00")
        p.read_bits("M", 0, 1)
        frame = _sent(p)
        subcmd = struct.unpack_from("<H", frame, 13)[0]
        self.assertEqual(subcmd, 0x0001)

    def test_write_bits_packing(self):
        """Bit values [1, 0, 1] must pack to bytes 0x10 0x10 (nibble pairs)."""
        p = _plc()
        p._sock.recv.side_effect = _bin_side()
        p.write_bits("Y", 0, [1, 0, 1])
        self.assertEqual(_sent(p)[-2:], b"\x10\x10")

    def test_device_code_X(self):
        p = _plc()
        p._sock.recv.side_effect = _bin_side(data=b"\x00\x00")
        p.read_words("X", 0, 1)
        self.assertIn(b"\x9c", _sent(p))

    def test_device_code_W(self):
        p = _plc()
        p._sock.recv.side_effect = _bin_side(data=b"\x00\x00")
        p.read_words("W", 0, 1)
        self.assertIn(b"\xb4", _sent(p))

    def test_device_lowercase_accepted(self):
        p = _plc()
        p._sock.recv.side_effect = _bin_side(data=b"\x00\x00")
        p.read_words("d", 0, 1)
        self.assertIn(b"\xa8", _sent(p))

    def test_custom_timer(self):
        """Timer parameter must appear in the frame."""
        p = MCProtocol3E("127.0.0.1", timer=0x0020)
        p._sock = MagicMock()
        p._sock.send.side_effect = lambda data: len(data)
        p._sock.recv.side_effect = _bin_side(data=b"\x00\x00")
        p.read_words("D", 0, 1)
        frame = _sent(p)
        timer = struct.unpack_from("<H", frame, 9)[0]
        self.assertEqual(timer, 0x0020)


# ── binary response parsing ───────────────────────────────────────────────────


class TestBinaryResponse(unittest.TestCase):

    def test_read_words_values(self):
        p = _plc()
        p._sock.recv.side_effect = _bin_side(data=b"\x0a\x00\x14\x00\x1e\x00")
        self.assertEqual(p.read_words("D", 0, 3), [10, 20, 30])

    def test_read_words_single(self):
        p = _plc()
        p._sock.recv.side_effect = _bin_side(data=b"\xff\xff")
        self.assertEqual(p.read_words("D", 0, 1), [0xFFFF])

    def test_read_bits_nibble_unpack(self):
        """
        Bit response bytes: each byte holds 2 bits in nibbles.
          byte 0x11 -> bit0 = hi nibble = 1, bit1 = lo nibble = 1
          byte 0x10 -> bit2 = hi nibble = 1, bit3 = lo nibble = 0
        """
        p = _plc()
        p._sock.recv.side_effect = _bin_side(data=b"\x11\x10")
        self.assertEqual(p.read_bits("M", 0, 4), [1, 1, 1, 0])

    def test_read_bits_odd_count(self):
        p = _plc()
        p._sock.recv.side_effect = _bin_side(data=b"\x10")
        self.assertEqual(p.read_bits("M", 0, 1), [1])

    def test_write_words_returns_none(self):
        p = _plc()
        p._sock.recv.side_effect = _bin_side()
        self.assertIsNone(p.write_words("D", 0, [0]))

    def test_write_bits_returns_none(self):
        p = _plc()
        p._sock.recv.side_effect = _bin_side()
        self.assertIsNone(p.write_bits("M", 0, [1]))


# ── ASCII mode ────────────────────────────────────────────────────────────────


class TestAsciiMode(unittest.TestCase):

    def test_read_words_frame_structure(self):
        p = _plc(mode="ascii")
        p._sock.recv.side_effect = _asc_side(data="0000")
        p.read_words("D", 100, 1)
        frame = _sent(p).decode()
        self.assertTrue(frame.startswith("500000FF03FF00"))
        self.assertIn("0401", frame)

    def test_read_words_d_decimal_addr(self):
        p = _plc(mode="ascii")
        p._sock.recv.side_effect = _asc_side(data="0001")
        p.read_words("D", 100, 1)
        self.assertIn("000100", _sent(p).decode())

    def test_read_words_x_hex_addr(self):
        p = _plc(mode="ascii")
        p._sock.recv.side_effect = _asc_side(data="0001")
        p.read_words("X", 0x10, 1)
        self.assertIn("000010", _sent(p).decode())

    def test_write_words_frame(self):
        p = _plc(mode="ascii")
        p._sock.recv.side_effect = _asc_side()
        p.write_words("D", 0, [0x00FF])
        frame = _sent(p).decode()
        self.assertIn("1401", frame)
        self.assertIn("00FF", frame)

    def test_read_words_values(self):
        p = _plc(mode="ascii")
        p._sock.recv.side_effect = _asc_side(data="000A0014001E")
        self.assertEqual(p.read_words("D", 0, 3), [10, 20, 30])

    def test_read_bits_values(self):
        p = _plc(mode="ascii")
        p._sock.recv.side_effect = _asc_side(data="1010")
        self.assertEqual(p.read_bits("M", 0, 4), [1, 0, 1, 0])

    def test_write_bits_frame(self):
        p = _plc(mode="ascii")
        p._sock.recv.side_effect = _asc_side()
        p.write_bits("M", 0, [1, 0, 1])
        self.assertIn("101", _sent(p).decode())

    def test_ascii_data_length_field(self):
        p = _plc(mode="ascii")
        p._sock.recv.side_effect = _asc_side(data="0000")
        p.read_words("D", 0, 1)
        frame = _sent(p).decode()
        stated_len = int(frame[14:18], 16)
        actual_len = len(frame[18:])
        self.assertEqual(stated_len, actual_len)


# ── error handling ────────────────────────────────────────────────────────────


class TestErrorHandling(unittest.TestCase):

    def test_binary_plc_error_type(self):
        """Non-zero end code must raise MCProtocolError with end_code attr."""
        p = _plc()
        p._sock.recv.side_effect = _bin_side(end_code=0xC059)
        with self.assertRaises(MCProtocolError) as ctx:
            p.read_words("D", 0, 1)
        self.assertEqual(ctx.exception.end_code, 0xC059)
        self.assertIn("C059", str(ctx.exception))

    def test_ascii_plc_error_type(self):
        p = _plc(mode="ascii")
        p._sock.recv.side_effect = _asc_side(end_code=0xC059)
        with self.assertRaises(MCProtocolError) as ctx:
            p.read_words("D", 0, 1)
        self.assertEqual(ctx.exception.end_code, 0xC059)

    def test_connection_error_type(self):
        """Not-connected must raise MCProtocolConnectionError (subclass of OSError)."""
        p = MCProtocol3E("127.0.0.1")
        with self.assertRaises(MCProtocolConnectionError):
            p.read_words("D", 0, 1)

    def test_connection_error_is_oserror(self):
        """MCProtocolConnectionError must be catchable as OSError."""
        p = MCProtocol3E("127.0.0.1")
        with self.assertRaises(OSError):
            p.read_words("D", 0, 1)

    def test_binary_zero_end_code_no_raise(self):
        p = _plc()
        p._sock.recv.side_effect = _bin_side(end_code=0, data=b"\x00\x00")
        p.read_words("D", 0, 1)  # must not raise

    def test_write_plc_error_raises(self):
        p = _plc()
        p._sock.recv.side_effect = _bin_side(end_code=0x0055)
        with self.assertRaises(MCProtocolError):
            p.write_words("D", 0, [1])

    def test_invalid_mode_raises(self):
        with self.assertRaises(ValueError):
            MCProtocol3E("127.0.0.1", mode="invalid")


# ── input validation ──────────────────────────────────────────────────────────


class TestValidation(unittest.TestCase):

    def test_unsupported_device_raises(self):
        p = _plc()
        with self.assertRaises(ValueError) as ctx:
            p.read_words("Q", 0, 1)
        self.assertIn("Q", str(ctx.exception))

    def test_negative_start_raises(self):
        p = _plc()
        with self.assertRaises(ValueError):
            p.read_words("D", -1, 1)

    def test_zero_count_raises(self):
        p = _plc()
        with self.assertRaises(ValueError):
            p.read_words("D", 0, 0)

    def test_valid_device_passes(self):
        """All known devices must pass validation without raising."""
        p = _plc()
        for dev in (
            "D",
            "W",
            "R",
            "ZR",
            "X",
            "Y",
            "M",
            "L",
            "B",
            "F",
            "SB",
            "SW",
            "TN",
            "CN",
            "Z",
        ):
            p._sock.recv.side_effect = _bin_side(data=b"\x00\x00")
            p.read_words(dev, 0, 1)

    def test_short_binary_payload_raises(self):
        """Binary read with truncated payload must raise MCProtocolConnectionError."""
        p = _plc()
        p._sock.recv.side_effect = _bin_side(
            data=b"\x01"
        )  # 1 byte, but count=2 needs 4
        with self.assertRaises(MCProtocolConnectionError):
            p.read_words("D", 0, 2)

    def test_short_ascii_payload_raises(self):
        """ASCII read with truncated payload must raise MCProtocolConnectionError."""
        p = _plc(mode="ascii")
        p._sock.recv.side_effect = _asc_side(data="00")  # 2 chars, but count=2 needs 8
        with self.assertRaises(MCProtocolConnectionError):
            p.read_words("D", 0, 2)


# ── connection lifecycle ──────────────────────────────────────────────────────


class TestConnection(unittest.TestCase):

    def test_close_sets_sock_none(self):
        p = _plc()
        p.close()
        self.assertIsNone(p._sock)

    def test_close_idempotent(self):
        p = _plc()
        p.close()
        p.close()

    @patch("mcprotocol.socket.socket")
    def test_context_manager_connect_close(self, mock_cls):
        mock_sock = MagicMock()
        mock_cls.return_value = mock_sock
        mock_sock.send.side_effect = lambda data: len(data)
        mock_sock.recv.side_effect = _bin_side(data=b"\x00\x00")
        with MCProtocol3E("192.168.1.1", port=1025) as plc:
            mock_sock.connect.assert_called_once_with(("192.168.1.1", 1025))
            mock_sock.settimeout.assert_called_once_with(5.0)
            plc.read_words("D", 0, 1)
        mock_sock.close.assert_called_once()

    @patch("mcprotocol.socket.socket")
    def test_context_manager_closes_on_exception(self, mock_cls):
        mock_sock = MagicMock()
        mock_cls.return_value = mock_sock
        try:
            with MCProtocol3E("192.168.1.1"):
                raise ValueError("test")
        except ValueError:
            pass
        mock_sock.close.assert_called_once()


if __name__ == "__main__":
    unittest.main(verbosity=2)
