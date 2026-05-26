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
    """Byte 0: V=2 -> 2 MSBs must be '10' (binary)."""
    pkt = RtpPacket()
    pkt.encode(2, 0, 0, 0, 1, 0, 26, 0, b'x')
    byte0 = pkt.header[0]
    assert (byte0 >> 6) == 2, f"2 MSBs of byte 0 wrong: {byte0 >> 6}"
    print("[PASS] test_header_byte0_format")


def test_marker_bit():
    """Marker bit must be set correctly in byte 1."""
    # marker=0
    pkt0 = RtpPacket()
    pkt0.encode(2, 0, 0, 0, 1, 0, 26, 0, b'data')
    assert (pkt0.header[1] >> 7) == 0, "Marker should be 0"

    # marker=1
    pkt1 = RtpPacket()
    pkt1.encode(2, 0, 0, 0, 1, 1, 26, 0, b'data')
    assert (pkt1.header[1] >> 7) == 1, "Marker should be 1"

    # PT must still be 26 with marker set
    assert pkt1.payloadType() == 26, f"PT wrong with marker: {pkt1.payloadType()}"
    print("[PASS] test_marker_bit")


def test_hd_video_stream_single_frame():
    """HDVideoStream must extract a single JPEG frame from SOI..EOI."""
    import tempfile
    from VideoStream import HDVideoStream

    # Craft a minimal MJPEG: SOI + payload + EOI
    frame_data = b'\xff\xd8' + b'\x00' * 100 + b'\xff\xd9'
    with tempfile.NamedTemporaryFile(suffix='.mjpeg', delete=False) as f:
        f.write(frame_data)
        tmpname = f.name

    try:
        vs = HDVideoStream(tmpname)
        frame = vs.nextFrame()
        assert frame == frame_data, f"Frame mismatch: {len(frame)} vs {len(frame_data)}"
        assert vs.frameNbr() == 1, f"frameNbr wrong: {vs.frameNbr()}"

        # No more frames
        frame2 = vs.nextFrame()
        assert frame2 == b'', "Should return empty after last frame"
    finally:
        vs.file.close()
        os.remove(tmpname)
    print("[PASS] test_hd_video_stream_single_frame")


def test_hd_video_stream_multiple_frames():
    """HDVideoStream must extract multiple JPEG frames."""
    import tempfile
    from VideoStream import HDVideoStream

    frame1 = b'\xff\xd8' + b'\x01' * 50 + b'\xff\xd9'
    frame2 = b'\xff\xd8' + b'\x02' * 200 + b'\xff\xd9'
    frame3 = b'\xff\xd8' + b'\x03' * 10 + b'\xff\xd9'

    with tempfile.NamedTemporaryFile(suffix='.mjpeg', delete=False) as f:
        f.write(frame1 + frame2 + frame3)
        tmpname = f.name

    try:
        vs = HDVideoStream(tmpname)
        r1 = vs.nextFrame()
        r2 = vs.nextFrame()
        r3 = vs.nextFrame()
        r4 = vs.nextFrame()

        assert r1 == frame1, "Frame 1 mismatch"
        assert r2 == frame2, "Frame 2 mismatch"
        assert r3 == frame3, "Frame 3 mismatch"
        assert r4 == b'', "Should return empty after last frame"
        assert vs.frameNbr() == 3, f"frameNbr wrong: {vs.frameNbr()}"
    finally:
        vs.file.close()
        os.remove(tmpname)
    print("[PASS] test_hd_video_stream_multiple_frames")


if __name__ == '__main__':
    print("=== Safety Net Tests ===\n")
    test_encode_decode_roundtrip()
    test_version_field()
    test_payload_type_mjpeg()
    test_sequence_number_boundaries()
    test_empty_payload()
    test_header_byte0_format()
    test_marker_bit()
    test_hd_video_stream_single_frame()
    test_hd_video_stream_multiple_frames()
    print("\n[PASS] All 9 tests passed")
