#!/usr/bin/env python3
import argparse, pymumble

def main():
    ap = argparse.ArgumentParser(description="Basic Mumblr client")
    ap.add_argument("--host", default="127.0.0.1", help="Server host (default 127.0.0.1)")
    ap.add_argument("--port", type=int, default=64738, help="Server port (default 64738)")
    ap.add_argument("--name", default="mumblr", help="Username (default mumblr)")
    ap.add_argument("--channel", default="My Channel", help="Channel to join")
    args = ap.parse_args()

    m = pymumble.Mumble(args.host, args.name, port=args.port, reconnect=True)
    m.start()
    m.is_ready()
    print(f"[Mumblr] Connected as {args.name}")

    for cid, ch in m.channels.items():
        if ch["name"] == args.channel:
            ch.move_in()
            print(f"[Mumblr] Joined channel: {args.channel}")
            break
    else:
        print(f"[Mumblr] Channel '{args.channel}' not found (staying in root)")

    try:
        m.join()
    except KeyboardInterrupt:
        print("\n[Mumblr] Disconnecting...")
        m.stop()

if __name__ == "__main__":
    main()
