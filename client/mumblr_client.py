#!/usr/bin/env python3
import os, argparse, numpy as np
import sounddevice as sd
import pymumble_py3 as pymumble
from pymumble_py3.callbacks import PYMUMBLE_CLBK_SOUNDRECEIVED

SAMPLE_RATE, CHANNELS, FRAME = 48000, 1, 960  # 20ms @ 48kHz

def parse_args():
    ap = argparse.ArgumentParser(description="Mumblr unified client (TX/RX/BOTH)")
    ap.add_argument("--host", default=os.getenv("HOST", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=int(os.getenv("PORT", "64738")))
    ap.add_argument("--name", default=os.getenv("USER_NAME", "mumblr"))
    ap.add_argument("--mode", choices=["rx","tx","both"], default=os.getenv("MODE","both"))
    ap.add_argument("--input",  default=os.getenv("ALSA_INPUT","hw:2,0"))
    ap.add_argument("--output", default=os.getenv("ALSA_OUTPUT","hw:2,0"))
    ap.add_argument("--channel", default=os.getenv("TARGET_CHANNEL",""))
    return ap.parse_args()

def main():
    a = parse_args()
    m = pymumble.Mumble(a.host, a.name, port=a.port, reconnect=True)
    m.set_receive_sound(a.mode in ("rx","both"))
    m.start(); m.is_ready()

    # Optional: join a channel by NAME
    if a.channel:
        ch = m.channels.find_by_name(a.channel)
        if ch:
            ch.move_in()
            print(f"[Mumblr] Joined channel: {a.channel}")
        else:
            print(f"[WARN] Channel '{a.channel}' not found; staying in current channel.")

    # RX path
    out = None
    if a.mode in ("rx","both"):
        out = sd.OutputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype="int16",
                              device=a.output, blocksize=FRAME)
        out.start()
        def on_sound(user, chunk):
            pcm = chunk.pcm
            data = np.frombuffer(pcm, dtype=np.int16) if isinstance(pcm, bytes) else np.asarray(pcm, dtype=np.int16)
            out.write(data)
        m.callbacks.set_callback(PYMUMBLE_CLBK_SOUNDRECEIVED, on_sound)
        print(f"[Mumblr RX] Playing to {a.output}")

    # TX path
    stream = None
    if a.mode in ("tx","both"):
        def mic_cb(indata, frames, time_info, status):
            if status:
                print(status)
            if frames:
                m.sound_output.add_sound(indata[:,0].tobytes())
        stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype="int16",
                                device=a.input, blocksize=FRAME, callback=mic_cb)
        stream.start()
        print(f"[Mumblr TX] Capturing from {a.input}")

    print(f"[Mumblr] Connected as {a.name} (mode={a.mode})")
    try:
        m.join()
    finally:
        if stream:
            stream.stop(); stream.close()
        if out:
            out.stop(); out.close()
        m.stop()

if __name__ == "__main__":
    main()
