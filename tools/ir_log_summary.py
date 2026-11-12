"""ir_log_summary.py <azahar_log.txt> [--packets N]: what a game and the emulated portal said to each other in one run,
from the patched Azahar's Service.IR lines: connections, the commands the game sent (after the three colour bytes) with
their counts, the blocks it read (Q) and wrote (W), the portal light's colours, figures put on, and the first N packets
with their replies in order (default 12). Stdlib only."""
import collections
import re
import sys

path = sys.argv[1]
show = 12
if "--packets" in sys.argv:
    show = int(sys.argv[sys.argv.index("--packets") + 1])

SENT = re.compile(r"\[\s*([\d.]+)\].*the game sent (\d+) bytes \(packet (\d+)\): ([0-9a-f ]+)")
REPLY = re.compile(r"\[\s*([\d.]+)\].*replying (\d+) bytes: ([0-9a-f ]+)")
NAMES = {0x52: "R (ready)", 0x41: "A (activate)", 0x43: "C (light)", 0x53: "S (status)", 0x51: "Q (read)",
         0x57: "W (write)", 0x4A: "J (side light)", 0x4C: "L (trap light)", 0x4D: "M (speaker)"}

events = []  # (time, kind, text)
commands = collections.Counter()
colours = collections.Counter()
reads, writes = [], []
first = []
connects = disconnects = autoconnections = 0
figures = []
with open(path, encoding="utf-8", errors="replace") as f:
    for line in f:
        if "Service.IR" not in line:
            continue
        if "AutoConnection" in line:
            autoconnections += 1
        if "Skylanders portal: connected" in line:
            connects += 1
        if "Skylanders portal: disconnected" in line:
            disconnects += 1
        if "figure on the portal" in line or "lifted" in line:
            m = re.search(r"\[\s*([\d.]+)\]", line)
            figures.append("%s s: %s" % (m.group(1) if m else "?", line.split("Skylanders portal: ", 1)[-1].strip()))
        m = SENT.search(line)
        if m:
            data = bytes.fromhex(m.group(4))
            body = data[3:]
            colours[data[:3].hex(" ")] += 1
            if body:
                commands[body[0]] += 1
                if body[0] == 0x51 and len(body) >= 3:
                    reads.append(body[2])
                if body[0] == 0x57 and len(body) >= 3:
                    writes.append(body[2])
            if len(first) < show * 2:
                first.append("%9s s  game  %s" % (m.group(1), data.hex(" ")))
            continue
        m = REPLY.search(line)
        if m and len(first) < show * 2:
            first.append("%9s s  reply %s" % (m.group(1), m.group(3).strip()))

print("AutoConnection calls: %d, connected %d, disconnected %d" % (autoconnections, connects, disconnects))
print("packets from the game: %d" % sum(commands.values()))
for code, count in commands.most_common():
    print("  %-16s %d" % (NAMES.get(code, "0x%02x" % code), count))
if reads:
    order = []
    for b in reads:
        if not order or order[-1] != b:
            order.append(b)
    print("blocks read (Q), in order: %s" % " ".join("%02x" % b for b in order[:80]))
if writes:
    print("blocks written (W): %s" % " ".join("%02x" % b for b in writes[:80]))
if colours:
    print("light colours (r g b) in front: %s" % ", ".join("%s x%d" % kv for kv in colours.most_common(6)))
for line in figures[:10]:
    print("figure: " + line)
if first:
    print("first packets:")
    for line in first:
        print("  " + line)
