#!/usr/bin/env python3
# Mumblr client with audio: specify headset devices and run rx/tx/both.
import os, argparse, numpy as np, queue
import pymumble_py3 as pymumble
import sounddevice as sd
from pymumble_py3.callbacks import PYMUMBLE_CLBK_SOUNDRECEIVED

SR         = 44100
CHANNELS   = 1
FRAME      = 960        # 20 ms @ 48 kHz
MAX_BUF_MS = 200        # cap RX buffer to avoid drift (drop oldest)

def parse_args():
    ap = argparse.ArgumentParser(description="Mumblr client (audio)")
    ap.add_argument("--host", default=os.getenv("HOST", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=int(os.getenv("PORT", "64738")))
    ap.add_argument("--name", default=os.getenv("USER_NAME", "mumblr"))
    ap.add_argument("--channel", default=os.getenv("TARGET_CHANNEL", "My Channel"))
    ap.add_argument("--mode", choices=["rx", "tx", "both"], default=os.getenv("MODE", "both"),
                    help="rx=playback only, tx=mic only, both=full duplex")
    ap.add_argument("--input", default=os.getenv("ALSA_INPUT", "hw:2,0"),
                    help="ALSA input device (mic), e.g. hw:2,0")
    ap.add_argument("--output", default=os.getenv("ALSA_OUTPUT", "hw:2,0"),
                    help="ALSA output device (headset), e.g. hw:2,0")
    ap.add_argument("--list-devices", action="store_true", help="List audio devices and exit")
    ap.add_argument("--max-buffer-ms", type=int, default=MAX_BUF_MS, help="RX buffer cap (ms)")
    return ap.parse_args()

def main():
    a = parse_args()

    if a.list_devices:
        print(sd.query_devices())
        return

    # Connect to Mumble
    m = pymumble.Mumble(a.host, a.name, port=a.port, reconnect=True)
    m.set_receive_sound(a.mode in ("rx", "both"))
    m.start()
    m.is_ready()
    print(f"[Mumblr] Connected as {a.name}")

    # Join channel by name (if present)
    ch = m.channels.find_by_name(a.channel)
    if ch:
        ch.move_in()
        print(f"[Mumblr] Joined channel: {a.channel}")
    else:
        print(f"[Mumblr] Channel '{a.channel}' not found; staying in root")

    # === RX path: drift-safe output via callback ===
    out = None
    rx_q = queue.Queue()
    max_frames_in_q = max(1, a.max_buffer_ms // 20)  # e.g., 200ms -> 10 frames of 20ms

    def on_sound(user, chunk):
        # push incoming network PCM as int16 array
        rx_q.put(np.frombuffer(chunk.pcm, dtype=np.int16))

    def out_cb(outdata, frames, time_info, status):
        # produce exactly 'frames' samples each callback
        needed = frames
        out_buf = np.empty((needed,), dtype=np.int16)

        # if queue too large, drop oldest to prevent drift
        try:
            while rx_q.qsize() > max_frames_in_q:
                rx_q.get_nowait()
        except queue.Empty:
            pass

        pos = 0
        while pos < needed:
            try:
                buf = rx_q.get_nowait()
            except queue.Empty:
                out_buf[pos:] = 0  # underrun → play silence
                break
            take = min(len(buf), needed - pos)
            out_buf[pos:pos + take] = buf[:take]
            pos += take
            if take < len(buf):
                # put remainder back at front (simple prepend)
                rest = buf[take:]
                # direct prepend: rebuild queue with rest first if available
                # (cheap way using internal queue—safe enough for CPython Queue)
                rx_q.queue.appendleft(rest)

        outdata[:] = out_buf.reshape(-1, 1)

    if a.mode in ("rx", "both"):
        m.callbacks.set_callback(PYMUMBLE_CLBK_SOUNDRECEIVED, on_sound)
        out = sd.OutputStream(
            samplerate=SR, channels=CHANNELS, dtype="int16",
            device=a.output, blocksize=FRAME, latency="low",
            callback=out_cb
        )
        out.start()
        print(f"[RX] → output device: {a.output} (drift-safe)")

    # === TX path: capture microphone from headset (exact 20ms frames) ===
    stream = None
    if a.mode in ("tx", "both"):
        def mic_cb(indata, frames, time_info, status):
            if status:
                print(status)
            if frames:
                m.sound_output.add_sound(indata[:, 0].tobytes())

        stream = sd.InputStream(
            samplerate=SR, channels=CHANNELS, dtype="int16",
            device=a.input, blocksize=FRAME, latency="low",
            callback=mic_cb
        )
        stream.start()
        print(f"[TX] ← input device: {a.input}")

    try:
        m.join()  # block
    except KeyboardInterrupt:
        pass
    finally:
        if stream:
            stream.stop(); stream.close()
        if out:
            out.stop(); out.close()
        m.stop()

if __name__ == "__main__":
    main()
