"""
@file test_rtp.py
@description Safety net — Unit tests cho RtpPacket.encode()/decode().
             Chạy: python test_rtp.py
             Tip Windows: set PYTHONUTF8=1 để bật UTF-8 mode nếu cần.
             Không cần GUI, không cần network.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from RtpPacket import RtpPacket, HEADER_SIZE


def test_encode_decode_roundtrip():
    """encode → decode phải idempotent (RFC 1889)."""
    payload = b'\xff\xd8\xff\xe0testdata\xff\xd9'
    pkt = RtpPacket()
    pkt.encode(version=2, padding=0, extension=0, cc=0,
               seqnum=42, marker=0, pt=26, ssrc=12345, payload=payload)

    raw = pkt.getPacket()
    assert len(raw) == HEADER_SIZE + len(payload), \
        f"Kích thước sai: {len(raw)} != {HEADER_SIZE + len(payload)}"

    pkt2 = RtpPacket()
    pkt2.decode(raw)

    assert pkt2.version() == 2,       f"Version sai: {pkt2.version()}"
    assert pkt2.seqNum() == 42,       f"SeqNum sai: {pkt2.seqNum()}"
    assert pkt2.payloadType() == 26,  f"PayloadType sai: {pkt2.payloadType()}"
    assert pkt2.getPayload() == payload, "Payload bị hỏng sau encode/decode"
    print("[PASS] test_encode_decode_roundtrip")


def test_version_field():
    """Version phải là 2 theo RFC 1889."""
    pkt = RtpPacket()
    pkt.encode(2, 0, 0, 0, 1, 0, 26, 0, b'data')
    assert pkt.version() == 2, f"Version sai: {pkt.version()}"
    print("[PASS] test_version_field")


def test_payload_type_mjpeg():
    """Payload type cho MJPEG phải là 26."""
    pkt = RtpPacket()
    pkt.encode(2, 0, 0, 0, 1, 0, 26, 0, b'data')
    assert pkt.payloadType() == 26, f"PayloadType sai: {pkt.payloadType()}"
    print("[PASS] test_payload_type_mjpeg")


def test_sequence_number_boundaries():
    """Sequence number 16-bit: 0 và 65535 phải lưu đúng."""
    for seqnum in [0, 255, 256, 65535]:
        pkt = RtpPacket()
        pkt.encode(2, 0, 0, 0, seqnum, 0, 26, 0, b'x')
        assert pkt.seqNum() == seqnum, \
            f"SeqNum={seqnum} bị lưu sai: {pkt.seqNum()}"
    print("[PASS] test_sequence_number_boundaries")


def test_empty_payload():
    """Encode payload rỗng không được crash."""
    pkt = RtpPacket()
    pkt.encode(2, 0, 0, 0, 1, 0, 26, 0, b'')
    assert pkt.getPayload() == b'', "Payload rỗng bị sai"
    assert len(pkt.getPacket()) == HEADER_SIZE, \
        f"Packet không đúng kích thước header: {len(pkt.getPacket())}"
    print("[PASS] test_empty_payload")


def test_header_byte0_format():
    """Byte 0: V=2 → 2 bit đầu phải là '10' (binary)."""
    pkt = RtpPacket()
    pkt.encode(2, 0, 0, 0, 1, 0, 26, 0, b'x')
    byte0 = pkt.header[0]
    assert (byte0 >> 6) == 2, f"2 bit đầu byte 0 sai: {byte0 >> 6}"
    print("[PASS] test_header_byte0_format")


if __name__ == '__main__':
    print("=== Safety Net Tests — RtpPacket ===\n")
    test_encode_decode_roundtrip()
    test_version_field()
    test_payload_type_mjpeg()
    test_sequence_number_boundaries()
    test_empty_payload()
    test_header_byte0_format()
    print("\n[PASS] Tat ca 6 tests deu thanh cong")
