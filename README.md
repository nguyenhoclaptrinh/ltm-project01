# Video Streaming with RTSP and RTP

Python demo for streaming MJPEG video with **RTSP** as the control protocol and **RTP** as the media transport. The project implements the client-side RTSP state machine, server-side RTP packetization, frame fragmentation, SD/HD transport switching, client buffering, and a Tkinter GUI for playback control.

## Features

- RTSP commands: `SETUP`, `PLAY`, `PAUSE`, `TEARDOWN`.
- RTP packetization with a 12-byte header, RTP version `2`, and MJPEG payload type `26`.
- Frame fragmentation for payloads larger than the MTU-safe payload size.
- RTP over UDP for `SD / UDP` mode.
- RTP over TCP interleaved for `HD / TCP` mode.
- Client-side pre-buffering with `queue.Queue`.
- Tkinter/ttk GUI with visible RTSP state, transport mode, session id, and buffer status.
- Server-side RTSP socket handling with `selectors.DefaultSelector()`.

## Project Structure

```text
.
├── docs/                         # Requirements, architecture notes, implementation plan, report
├── Project_01/                   # Original assignment assets
├── src/python_rtp/
│   ├── Client.py                 # GUI client, RTSP requests, RTP receive/buffer logic
│   ├── ClientLauncher.py         # Client entry point
│   ├── Server.py                 # RTSP server using selectors
│   ├── ServerWorker.py           # RTSP session handling and RTP streaming
│   ├── RtpPacket.py              # RTP encode/decode
│   ├── VideoStream.py            # MJPEG frame readers
│   ├── movie.Mjpeg               # Sample video
│   ├── requirements.txt          # Python dependencies
│   └── test_rtp.py               # Unit tests
└── README.md
```

## Getting Started

Install dependencies:

```bash
pip install -r src/python_rtp/requirements.txt
```

Start the server:

```bash
cd src/python_rtp
python Server.py 8554
```

Start the client in another terminal:

```bash
cd src/python_rtp
python ClientLauncher.py localhost 8554 26000 movie.Mjpeg
```

## Usage

1. Select `SD / UDP` or `HD / TCP`.
2. Click `Setup`.
3. Click `Play`.
4. Use `Pause` and `Play` to pause/resume.
5. Click `Teardown` to close the RTSP session and clean temporary frame cache.

The GUI status bar shows the current RTSP state, transport mode, session id, and buffer level.

## Streaming Modes

| Mode | Transport | Description |
|---|---|---|
| `SD / UDP` | RTP over UDP | Client sends `Transport: RTP/UDP; client_port=...`; server sends RTP packets to the selected UDP port. |
| `HD / TCP` | RTP over TCP interleaved | Client sends `Transport: RTP/TCP`; server sends RTP frames through the RTSP TCP socket using `$ | channel | length | RTP data`. |

Both modes can use the same sample file, so visual quality may look the same unless a separate HD video file is provided. In this implementation, the main difference is the transport mechanism.

## Testing

Run unit tests:

```bash
cd src/python_rtp
python test_rtp.py
```

Check Python syntax:

```bash
python -m py_compile Client.py Server.py ServerWorker.py RtpPacket.py VideoStream.py ClientLauncher.py test_rtp.py
```

Expected result:

- All 9 tests in `test_rtp.py` pass.
- `py_compile` exits without errors.

## Assignment Mapping

| Requirement | Main files |
|---|---|
| RTSP client, RTP packetization, UDP, fragmentation | `Client.py`, `ServerWorker.py`, `RtpPacket.py` |
| I/O multiplexing | `Server.py` |
| HD streaming with TCP | `Client.py`, `ServerWorker.py`, `VideoStream.py` |
| Client-side caching and SD/HD switching | `Client.py` |
| Report | `docs/Report.md` |

## Documentation

- Assignment brief: `Project Socket Programming.md`
- Technical report: `docs/Report.md`
- Architecture notes: `docs/020-architecture/`
- Implementation notes: `docs/040-implementation/`

## Notes

- Runtime frame cache files use the pattern `cache-*.jpg` and are ignored by Git.
- Server and client consoles print RTSP requests, sessions, and selected transport mode for demo/debugging.
