import sys, Ice
Ice.loadSlice(f"-I{Ice.getSliceDir()} /usr/share/slice/Murmur.ice")
import Murmur

with Ice.initialize(sys.argv) as ic:
    meta = Murmur.MetaPrx.checkedCast(ic.stringToProxy("Meta:tcp -h 127.0.0.1 -p 6502"))
    server = (meta.getAllServers() or [meta.newServer()])[0]
    for cid, ch in server.getChannels().items():
        if ch.name == "My Channel" and ch.parent == 0:
            print("Channel exists", cid); break
    else:
        print("Channel created", server.addChannel("My Channel", 0))
