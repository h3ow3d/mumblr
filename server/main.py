#!/usr/bin/env python3

import sys, argparse, Ice

SLICE     = "/usr/share/slice/Murmur.ice"
ENDPOINT  = "Meta:tcp -h 127.0.0.1 -p 6502"
DEFAULT_CHANNEL = "My Channel"
DEFAULT_PARENT  = 0

def main():
    ap = argparse.ArgumentParser(description="Basic Murmur ICE channel ensure (no secrets)")
    ap.add_argument("--channel", default=DEFAULT_CHANNEL, help="channel name to ensure")
    ap.add_argument("--parent", type=int, default=DEFAULT_PARENT, help="parent channel id (0=root)")
    args = ap.parse_args()

    Ice.loadSlice(f"-I{Ice.getSliceDir()} {SLICE}")
    import Murmur

    with Ice.initialize(sys.argv) as ic:
        meta = Murmur.MetaPrx.checkedCast(ic.stringToProxy(ENDPOINT))
        if not meta:
            raise SystemExit("Cannot connect to Murmur ICE endpoint")

        servers = meta.getAllServers()
        server = servers[0] if servers else meta.newServer()

        for cid, ch in server.getChannels().items():
            if ch.name == args.channel and ch.parent == args.parent:
                print(f"Channel exists (id={cid})")
                break
        else:
            cid = server.addChannel(args.channel, args.parent)
            print(f"Channel created (id={cid})")

if __name__ == "__main__":
    main()
