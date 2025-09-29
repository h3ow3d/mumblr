#!/usr/bin/env python3
import os, sys
import configparser

def load_env_file(path="/etc/mumblr-ice.env"):
    if not os.path.exists(path):
        return
    # parse simple KEY=VALUE file
    with open(path) as f:
        for line in f:
            line=line.strip()
            if not line or line.startswith("#") or "=" not in line: 
                continue
            k,v = line.split("=",1)
            os.environ.setdefault(k.strip(), v.strip())

load_env_file()

ICE_ENDPOINT = os.getenv("ICE_ENDPOINT", "Meta:tcp -h 127.0.0.1 -p 6502")
ICE_SECRET   = os.getenv("ICE_SECRET")
SLICE        = os.getenv("SLICE", "/usr/share/slice/Murmur.ice")
CHANNEL_NAME = os.getenv("TARGET_CHANNEL", "My Channel")
PARENT_ID    = int(os.getenv("PARENT_ID", "0"))

if not ICE_SECRET:
    print("ERROR: ICE_SECRET not set. Set it in /etc/mumblr-ice.env or env.", file=sys.stderr)
    sys.exit(2)

import Ice
# Put secret into default context so all calls carry it
with Ice.initialize([f'--Ice.Default.Context.icesecret={ICE_SECRET}'] + sys.argv) as ic:
    Ice.loadSlice(f"-I{Ice.getSliceDir()} {SLICE}")
    import Murmur

    meta = Murmur.MetaPrx.checkedCast(ic.stringToProxy(ICE_ENDPOINT))
    if not meta:
        raise SystemExit("Cannot connect to Murmur ICE endpoint")

    servers = meta.getAllServers()
    server = servers[0] if servers else meta.newServer()

    # ensure single channel
    for cid, ch in server.getChannels().items():
        if ch.name == CHANNEL_NAME and ch.parent == PARENT_ID:
            print(f"[Mumblr ICE] Channel exists (id={cid})")
            break
    else:
        cid = server.addChannel(CHANNEL_NAME, PARENT_ID)
        print(f"[Mumblr ICE] Channel created (id={cid})")
