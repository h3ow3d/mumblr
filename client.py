#!/usr/bin/env python3
import os, argparse, pymumble_py3 as pymumble, sounddevice as sd

def parse_args():
    ap = argparse.ArgumentParser(description="Mumblr unified client (TX/RX)")
    ap.add_argument("--host", default=os.getenv("HOST", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=int(os.getenv("PORT", "64738")))
    ap.add_argument("--name", default=os.getenv("USER_NAME", "mumblr"))
    ap.add_argument("--mode", choices=["rx","tx","both"], default=os.getenv("MODE","both"))
    ap.add_argument("--input", default=os.getenv("ALSA_INPUT","hw:2,0"), help="ALSA device for mic")
    ap.add_argument("--output", default=os.getenv("ALSA_OUTPUT","hw:2,0"), help="ALSA device for playback")
    return ap.parse_args()

def main():
    args = parse_args()

    m = pymumble.Mumble(args.host, args.name, port=args.port, reconnect=True)
    m.start()
    m.is_ready()

    # RX path
    if args.mode in ("rx","both"):
        def pcm_handler(user, soundchunk):
            sd.play(soundchunk.pcm, samplerate=48000, device=args.output, blocking=False)
        m.set_receive_sound(True)
        m.callbacks.set_callback("sound_received", pcm_handler)
        print(f"[Mumblr RX] Listening → {args.output}")

    # TX path
    if args.mode in ("tx","both"):
        def callback(indata, frames, time, status):
            if status: print(status)
            pcm = indata.copy()
            m.sound_output.add_sound(pcm)

        stream = sd.InputStream(channels=1, samplerate=48000,
                                dtype="int16", device=args.input,
                                callback=callback)
        stream.start()
        print(f"[Mumblr TX] Sending mic → {args.input}")

    print(f"[Mumblr] Connected as {args.name} ({args.mode})")
    m.join()

if __name__ == "__main__":
    main()
