#!/usr/bin/env python3
# Mumblr client with audio: specify headset devices and run rx/tx/both.
import os, argparse, numpy as np, queue
import pymumble_py3 as pymumble
import sounddevice as sd
from pymumble_py3.callbacks import PYMUMBLE_CLBK_SOUNDRECEIVED

# Stable combo for RPi + H340:
SR         = 44100
CHANNELS   = 1
FRAME      = 960                # ~21.8 ms @ 44.1 kHz (more headroom, fewer XRUNs)
MAX_BUF_MS = 200                # cap RX buffer to avoid drift (drop oldest)

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
    ap.add_argument("--gate", type=int, default=0,
                    help="Noise gate RMS threshold (0-32767). 0=off")
    ap.add_argument("--highpass", type=float, default=0.0,
                    help="High-pass filter cutoff in Hz (0=off)")
    return ap.parse_args()

def rms_i16(x: np.ndarray) -> int:
    if x.size == 0:
        return 0
    return int(np.sqrt(np.mean((x.astype(np.int32))**2)))

class HighPass:
    """Simple one-pole high-pass: y[n]=α*(y[n-1]+x[n]-x[n-1])."""
    def __init__(self, cutoff_hz: float, sr: int):
        self.enabled = cutoff_hz > 0
        self.prev_x = 0.0
        self.prev_y = 0.0
        if self.enabled:
            rc = 1.0 / (2 * np.pi * cutoff_hz)
            self.alpha = rc / (rc + 1.0/sr)
    def process(self, x: np.ndarray) -> np.ndarray:
        if not self.enabled:
            return x
        y = np.empty_like(x, dtype=np.float32)
        px, py, a = self.prev_x, self.prev_y, self.alpha
        xf = x.astype(np.float32, copy=False)
        for i in range(xf.shape[0]):
            xi = xf[i]
            yi = a * (py + xi - px)
            y[i] = yi
            px, py = xi, yi
        self.prev_x, self.prev_y = px, py
        # clamp back to int16
        y = np.clip(y, -32768, 32767).astype(np.int16)
        return y

def main():
    a = parse_args()

    if a.list_devices:
        print(sd.query_devices()); return

    # Connect to Mumble
    m = pymumble.Mumble(a.host, a.name, port=a.port, reconnect=True)
    m.set_receive_sound(a.mode in ("rx", "both"))
    m.start(); m.is_ready()
    print(f"[Mumblr] Connected as {a.name}")

    # Join channel by name (if present)
    ch = m.channels.find_by_name(a.channel)
    if ch: ch.move_in(); print(f"[Mumblr] Joined channel: {a.channel}")
    else:  print(f"[Mumblr] Channel '{a.channel}' not found; staying in root")

    # === RX path: drift-safe output via callback ===
    out = None
    rx_q = queue.Queue()
    max_frames_in_q = max(1, a.max_buffer_ms // int(1000 * FRAME / SR))  # ~ms->frames

    def on_sound(user, chunk):
        rx_q.put(np.frombuffer(chunk.pcm, dtype=np.int16))

    def out_cb(outdata, frames, time_info, status):
        needed = frames
        out_buf = np.empty((needed,), dtype=np.int16)

        # cap queue size to bound latency
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
                out_buf[pos:] = 0
                break
            take = min(len(buf), needed - pos)
            out_buf[pos:pos + take] = buf[:take]
            pos += take
            if take < len(buf):
                rx_q.queue.appendleft(buf[take:])  # put remainder back

        outdata[:] = out_buf.reshape(-1, 1)

    if a.mode in ("rx", "both"):
        m.callbacks.set_callback(PYMUMBLE_CLBK_SOUNDRECEIVED, on_sound)
        out = sd.OutputStream(
            samplerate=SR, channels=CHANNELS, dtype="int16",
            device=a.output, blocksize=FRAME, latency="low",
            callback=out_cb
        )
        out.start()
        print(f"[RX] → {a.output} @ {SR} Hz (frame={FRAME}, drift-safe)")

    # === TX path: microphone capture ===
    hp = HighPass(a.highpass, SR) if a.highpass > 0 else None
    stream = None
    if a.mode in ("tx", "both"):
        def mic_cb(indata, frames, time_info, status):
            if frames:
                mono = indata[:, 0]
                if hp: mono = hp.process(mono)
                if a.gate > 0 and rms_i16(mono) < a.gate:
                    m.sound_output.add_sound(b"\x00\x00" * frames)  # silence
                else:
                    m.sound_output.add_sound(mono.tobytes())

        stream = sd.InputStream(
            samplerate=SR, channels=CHANNELS, dtype="int16",
            device=a.input, blocksize=FRAME, latency="low",
            callback=mic_cb
        )
        stream.start()
        info = []
        if a.gate: info.append(f"gate={a.gate}")
        if a.highpass: info.append(f"highpass={int(a.highpass)}Hz")
        extra = f" ({', '.join(info)})" if info else ""
        print(f"[TX] ← {a.input} @ {SR} Hz (frame={FRAME}){extra}")

    try:
        m.join()
    except KeyboardInterrupt:
        pass
    finally:
        if stream: stream.stop(); stream.close()
        if out:    out.stop(); out.close()
        m.stop()

if __name__ == "__main__":
    main()
