#!/usr/bin/env python3
# Mumblr client with audio: specify headset devices and run rx/tx/both.
import os, argparse, numpy as np
import pymumble_py3 as pymumble
import sounddevice as sd
from pymumble_py3.callbacks import PYMUMBLE_CLBK_SOUNDRECEIVED

CHANNELS    = 1
FRAME       = 960

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

    # === RX path: play received audio to headset ===
    out = None
    if a.mode in ("rx", "both"):
        out = sd.OutputStream(channels=CHANNELS, dtype="int16",
                              device=a.output, blocksize=FRAME)
        out.start()

        def on_sound(user, chunk):
            # chunk.pcm is bytes (int16 little-endian)
            out.write(np.frombuffer(chunk.pcm, dtype=np.int16))

        m.callbacks.set_callback(PYMUMBLE_CLBK_SOUNDRECEIVED, on_sound)
        print(f"[RX] → output device: {a.output}")

    # === TX path: capture microphone from headset ===
    stream = None
    if a.mode in ("tx", "both"):
        def mic_cb(indata, frames, time_info, status):
            if status:
                print(status)
            if frames:
                # int16 mono 20ms frames as bytes
                m.sound_output.add_sound(indata[:, 0].tobytes())

        stream = sd.InputStream(channels=CHANNELS, dtype="int16",
                                device=a.input, blocksize=FRAME, callback=mic_cb)
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
