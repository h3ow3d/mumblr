#!/usr/bin/env python3
# Mumblr client with audio: specify headset devices and run rx/tx/both + fun TX FX.
import os, argparse, numpy as np, queue
import pymumble_py3 as pymumble
import sounddevice as sd
from pymumble_py3.callbacks import PYMUMBLE_CLBK_SOUNDRECEIVED

# Stable combo for RPi + H340:
SR         = 44100
CHANNELS   = 1
FRAME      = 960                # ~21.8 ms @ 44.1 kHz (extra headroom)
MAX_BUF_MS = 200

def parse_args():
    ap = argparse.ArgumentParser(description="Mumblr client (audio + FX)")
    ap.add_argument("--host", default=os.getenv("HOST", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=int(os.getenv("PORT", "64738")))
    ap.add_argument("--name", default=os.getenv("USER_NAME", "mumblr"))
    ap.add_argument("--channel", default=os.getenv("TARGET_CHANNEL", "My Channel"))
    ap.add_argument("--mode", choices=["rx", "tx", "both"], default=os.getenv("MODE", "both"))
    ap.add_argument("--input", default=os.getenv("ALSA_INPUT", "hw:2,0"))
    ap.add_argument("--output", default=os.getenv("ALSA_OUTPUT", "hw:2,0"))
    ap.add_argument("--list-devices", action="store_true")
    ap.add_argument("--max-buffer-ms", type=int, default=MAX_BUF_MS)

    # Noise control
    ap.add_argument("--gate", type=int, default=0, help="Noise gate RMS (0=off)")
    ap.add_argument("--highpass", type=float, default=0.0, help="TX high-pass Hz (0=off)")

    # Fun FX (TX only)
    ap.add_argument("--fx",
                    choices=["none","radio","robot","echo","bitcrush","vader"],
                    default=os.getenv("FX","none"),
                    help="Voice FX for TX")
    # FX params (sensible defaults)
    ap.add_argument("--fx-robot-hz", type=float, default=90.0)
    ap.add_argument("--fx-echo-ms", type=int, default=140)
    ap.add_argument("--fx-echo-fb", type=float, default=0.25)
    ap.add_argument("--fx-echo-mix", type=float, default=0.25)
    ap.add_argument("--fx-bitcrush-bits", type=int, default=6)
    return ap.parse_args()

def rms_i16(x: np.ndarray) -> int:
    if x.size == 0: return 0
    return int(np.sqrt(np.mean((x.astype(np.int32))**2)))

# ---------- Simple 1-pole filters ----------
class HighPass:
    def __init__(self, cutoff_hz: float, sr: int):
        self.enabled = cutoff_hz > 0
        self.x1 = 0.0; self.y1 = 0.0
        if self.enabled:
            rc = 1.0/(2*np.pi*cutoff_hz)
            self.a = rc/(rc + 1.0/sr)
    def process(self, x: np.ndarray) -> np.ndarray:
        if not self.enabled: return x
        y = np.empty_like(x, dtype=np.float32)
        a = self.a; x1 = self.x1; y1 = self.y1
        xf = x.astype(np.float32, copy=False)
        for i in range(xf.size):
            xi = xf[i]
            yi = a*(y1 + xi - x1)
            y[i] = yi
            x1, y1 = xi, yi
        self.x1, self.y1 = x1, y1
        return np.clip(y, -32768, 32767).astype(np.int16)

class LowPass:
    def __init__(self, cutoff_hz: float, sr: int):
        self.enabled = cutoff_hz > 0
        self.y1 = 0.0
        if self.enabled:
            rc = 1.0/(2*np.pi*cutoff_hz)
            self.a = 1.0/(1.0 + rc*sr)  # simple 1-pole LP
    def process(self, x: np.ndarray) -> np.ndarray:
        if not self.enabled: return x
        y = np.empty_like(x, dtype=np.float32)
        a = self.a; y1 = self.y1
        xf = x.astype(np.float32, copy=False)
        for i in range(xf.size):
            y1 = y1 + a*(xf[i] - y1)
            y[i] = y1
        self.y1 = y1
        return np.clip(y, -32768, 32767).astype(np.int16)

# ---------- Fun FX ----------
class RingMod:
    def __init__(self, freq_hz: float, sr: int):
        self.freq = float(freq_hz); self.sr = sr; self.phase = 0.0
        self.k = 2*np.pi*self.freq/self.sr
    def process(self, x: np.ndarray) -> np.ndarray:
        n = x.size
        # build sin with preserved phase
        t = self.phase + self.k*np.arange(n, dtype=np.float32)
        self.phase = (self.phase + self.k*n) % (2*np.pi)
        mod = np.sin(t)
        y = (x.astype(np.float32) * mod).astype(np.int32)
        return np.clip(y, -32768, 32767).astype(np.int16)

class Echo:
    def __init__(self, delay_ms: int, sr: int, fb: float=0.25, mix: float=0.25):
        self.len = max(1, int(sr*delay_ms/1000))
        self.buf = np.zeros(self.len, dtype=np.float32)
        self.pos = 0; self.fb = float(fb); self.mix = float(mix)
    def process(self, x: np.ndarray) -> np.ndarray:
        xf = x.astype(np.float32)
        out = np.empty_like(xf)
        for i in range(xf.size):
            d = self.buf[self.pos]
            y = xf[i] + self.mix*d
            out[i] = y
            self.buf[self.pos] = xf[i] + self.fb*d
            self.pos = (self.pos + 1) % self.len
        return np.clip(out, -32768, 32767).astype(np.int16)

def build_fx_chain(a):
    chain = []
    # Optional high-pass first (hum/rumble cut)
    if a.highpass > 0:
        chain.append(HighPass(a.highpass, SR))
    # Selected fun FX
    if a.fx == "radio":
        chain.append(HighPass(300, SR))
        chain.append(LowPass(3400, SR))
    elif a.fx == "robot":
        chain.append(RingMod(a.fx_robot_hz, SR))
    elif a.fx == "echo":
        chain.append(Echo(a.fx_echo_ms, SR, fb=a.fx_echo_fb, mix=a.fx_echo_mix))
    elif a.fx == "bitcrush":
        # inline bitcrush as a lambda (reduce resolution)
        levels = max(2, 1 << max(1, min(15, a.fx_bitcrush_bits)))
        step = int(np.round(65536 / levels))
        half = 32768
        chain.append(lambda x: (np.round((x.astype(np.int32)+half)/step)*step - half).clip(-32768,32767).astype(np.int16))
    elif a.fx == "vader":
        chain.append(RingMod(70.0, SR))
        chain.append(LowPass(1500, SR))
    return chain

def apply_chain(x: np.ndarray, chain):
    y = x
    for f in chain:
        y = f.process(y) if hasattr(f, "process") else f(y)
    return y

def main():
    a = parse_args()
    if a.list_devices:
        print(sd.query_devices()); return

    # Connect
    m = pymumble.Mumble(a.host, a.name, port=a.port, reconnect=True)
    m.set_receive_sound(a.mode in ("rx","both"))
    m.start(); m.is_ready()
    print(f"[Mumblr] Connected as {a.name}")

    # Join channel
    ch = m.channels.find_by_name(a.channel)
    if ch: ch.move_in(); print(f"[Mumblr] Joined channel: {a.channel}")
    else:  print(f"[Mumblr] Channel '{a.channel}' not found; staying in root")

    # === RX (drift-safe) ===
    out = None
    rx_q = queue.Queue()
    max_frames_in_q = max(1, a.max_buffer_ms // int(1000*FRAME/SR))

    def on_sound(user, chunk):
        rx_q.put(np.frombuffer(chunk.pcm, dtype=np.int16))

    def out_cb(outdata, frames, time_info, status):
        needed = frames
        out_buf = np.empty((needed,), dtype=np.int16)
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
                out_buf[pos:] = 0; break
            take = min(len(buf), needed-pos)
            out_buf[pos:pos+take] = buf[:take]
            pos += take
            if take < len(buf):
                rx_q.queue.appendleft(buf[take:])
        outdata[:] = out_buf.reshape(-1,1)

    if a.mode in ("rx","both"):
        m.callbacks.set_callback(PYMUMBLE_CLBK_SOUNDRECEIVED, on_sound)
        out = sd.OutputStream(samplerate=SR, channels=CHANNELS, dtype="int16",
                              device=a.output, blocksize=FRAME, latency="low",
                              callback=out_cb)
        out.start()
        print(f"[RX] → {a.output} @ {SR} Hz (frame={FRAME})")

    # === TX (mic + FX) ===
    fx_chain = build_fx_chain(a)
    stream = None
    if a.mode in ("tx","both"):
        def mic_cb(indata, frames, time_info, status):
            if frames == 0: return
            mono = indata[:,0]
            if fx_chain:
                mono = apply_chain(mono, fx_chain)
            if a.gate > 0 and rms_i16(mono) < a.gate:
                m.sound_output.add_sound(b"\x00\x00"*frames)
            else:
                m.sound_output.add_sound(mono.tobytes())

        stream = sd.InputStream(samplerate=SR, channels=CHANNELS, dtype="int16",
                                device=a.input, blocksize=FRAME, latency="low",
                                callback=mic_cb)
        stream.start()
        tags = []
        if a.fx != "none": tags.append(f"fx={a.fx}")
        if a.gate: tags.append(f"gate={a.gate}")
        if a.highpass: tags.append(f"hp={int(a.highpass)}Hz")
        extra = f" ({', '.join(tags)})" if tags else ""
        print(f"[TX] ← {a.input} @ {SR} Hz (frame={FRAME}){extra}")

    try:
        m.join()
    except KeyboardInterrupt:
        pass
    finally:
        if stream: stream.stop(); stream.close()
        if out: out.stop(); out.close()
        m.stop()

if __name__ == "__main__":
    main()
