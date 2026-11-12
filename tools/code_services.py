"""code_services.py [--code-out <folder>] <game.cci> [<game.cci> ...]: what a decrypted 3DS game asks for, read
without running it.

For each dump (read only): the services its exheader allows (the ARM11 service access list: ir:USER for the
infrared portal, nfc:u for the New 3DS reader, ...), and in its program code (ExeFS .code, decompressed when the
exheader says so) the ir:USER command headers it builds (InitializeIrNopShared 0x00180182, AutoConnection
0x000702C0, ...) and the service names it opens. A command header found in the code is a hint, not proof: the same
32-bit value can be other data, and a header put together from instructions instead of loaded is not seen. --code-out writes the decompressed code as <program id>.code.bin into a folder of the caller's
(it is the game's code: a local folder, never a repository); it is loaded at 0x00100000. Stdlib only.
"""
import os
import struct
import sys

MEDIA = 0x200

# ir:USER command headers (3dbrew "IR Services"): (command id << 16) | (normal words << 6) | translate words.
IR_USER = {
    0x00010182: "InitializeIrNop",
    0x000500C0: "WaitConnection",
    0x00060040: "RequireConnection",
    0x000702C0: "AutoConnection",
    0x00080000: "AnyConnection",
    0x00090000: "Disconnect",
    0x000A0000: "GetReceiveEvent",
    0x000B0000: "GetSendEvent",
    0x000C0000: "GetConnectionStatusEvent",
    0x000D0042: "SendIrNop",
    0x000E0042: "SendIrNopLarge",
    0x000F0040: "ReceiveIrnop",
    0x00100042: "ReceiveIrnopLarge",
    0x00110040: "GetLatestReceiveErrorResult",
    0x00120040: "GetLatestSendErrorResult",
    0x00130000: "GetConnectionStatus",
    0x00140000: "GetTryingToConnectStatus",
    0x00180182: "InitializeIrNopShared",
    0x00190040: "ReleaseReceivedData",
    0x001A0040: "SetOwnMachineId",
}
NAMES = [b"ir:USER", b"ir:rst", b"ir:u", b"nfc:u", b"nfc:m", b"nfc:dev", b"mvd:STD", b"hid:SPVR", b"hid:USER"]


def read(f, offset, size):
    f.seek(offset)
    return f.read(size)


def blz_decompress(data):
    """The ExeFS .code compression (backward LZ77, as 3dstool and ctrtool undo it)."""
    top_bottom, extra = struct.unpack_from("<II", data, len(data) - 8)
    out = bytearray(data) + bytearray(extra)
    src = len(data) - (top_bottom >> 24)
    dst = len(out)
    end = len(data) - (top_bottom & 0xFFFFFF)
    while src > end:
        src -= 1
        flags = data[src]
        for bit in range(8):
            if flags & (0x80 >> bit):
                src -= 2
                pair = data[src] | data[src + 1] << 8
                disp = (pair & 0x0FFF) + 3
                for _ in range((pair >> 12) + 3):
                    dst -= 1
                    out[dst] = out[dst + disp]
            else:
                src -= 1
                dst -= 1
                out[dst] = data[src]
            if src <= end:
                break
    return bytes(out)


def look(path, code_out=None):
    with open(path, "rb") as f:
        if read(f, 0x100, 4) != b"NCSD":
            print(path, ": not a CCI (no NCSD header)")
            return
        part0, _ = struct.unpack_from("<II", read(f, 0x120, 8))
        ncch = part0 * MEDIA
        head = read(f, ncch, 0x200)
        if head[0x100:0x104] != b"NCCH":
            print(path, ": partition 0 is not an NCCH")
            return
        if not head[0x18F] & 0x4:
            print(path, ": encrypted (NoCrypto not set); this tool reads decrypted dumps only")
            return
        program_id = struct.unpack_from("<Q", head, 0x118)[0]
        product = head[0x150:0x160].rstrip(b"\0").decode("ascii", "replace")
        exh = read(f, ncch + 0x200, 0x800)
        compressed = exh[0xD] & 1
        services = [exh[0x250 + 8 * i:0x258 + 8 * i].rstrip(b"\0").decode("ascii", "replace") for i in range(34)]
        services += [exh[0x360 + 8 * i:0x368 + 8 * i].rstrip(b"\0").decode("ascii", "replace") for i in range(2)]
        exefs_off = struct.unpack_from("<I", head, 0x1A0)[0] * MEDIA
        exefs = read(f, ncch + exefs_off, 0x200)
        code = None
        for i in range(10):
            name, off, size = struct.unpack_from("<8sII", exefs, i * 16)
            if name.rstrip(b"\0") == b".code":
                code = read(f, ncch + exefs_off + 0x200 + off, size)
    print("==", path.replace("\\", "/").split("/")[-1])
    print("  program id %016X, product code %s, code %s" % (program_id, product, "compressed" if compressed else "plain"))
    print("  services:", ", ".join(s for s in services if s))
    if code is None:
        print("  no .code in the ExeFS")
        return
    if compressed:
        code = blz_decompress(code)
    print("  code: %d bytes" % len(code))
    if code_out:
        out = os.path.join(code_out, "%016X.code.bin" % program_id)
        with open(out, "wb") as f:
            f.write(code)
        print("  written:", out)
    for name in NAMES:
        hits = []
        start = 0
        while True:
            at = code.find(name + b"\0", start)
            if at < 0:
                break
            hits.append(at)
            start = at + 1
        if hits:
            print("  name %-9s at %s" % (name.decode(), ", ".join("0x%X" % h for h in hits[:6])))
    words = {}
    for at in range(0, len(code) - 3, 4):
        value = struct.unpack_from("<I", code, at)[0]
        if value in IR_USER:
            words.setdefault(value, []).append(at)
    for value in sorted(words):
        at = words[value]
        print("  ir:USER %-24s 0x%08X: %d word(s), first at 0x%X" % (IR_USER[value], value, len(at), at[0]))


if __name__ == "__main__":
    args = sys.argv[1:]
    code_out = None
    if len(args) >= 2 and args[0] == "--code-out":
        code_out = args[1]
        args = args[2:]
    if not args:
        print(__doc__)
        sys.exit(1)
    for p in args:
        look(p, code_out)
