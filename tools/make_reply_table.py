"""make_reply_table.py <figure .dump> <out .txt> [--status XX]: a reply table for the 3DS portal experiments
(SKYLANDERS_PORTAL_REPLIES): the answers that got Giants 3DS to "Place a toy" (R, A, S), the status with slot 0's
state XX (03 = just put on, 01 = on it; default 03), and every block of the figure for the read command
'Q' (requests ff ff ff 51 <00|10|20> <block>), answered as skylanders-portal's SoftwarePortal does:
51, 0x10 | slot, block, 16 bytes. Only reads the figure file."""
import pathlib
import sys

figure = pathlib.Path(sys.argv[1]).read_bytes()
assert len(figure) == 1024, len(figure)
out = pathlib.Path(sys.argv[2])
status = "03"
if "--status" in sys.argv:
    status = sys.argv[sys.argv.index("--status") + 1]
lines = [
    f"# made by make_reply_table.py from {pathlib.Path(sys.argv[1]).name}",
    "ff ff ff 52 => 52 02 1b",
    "ff ff ff 41 01 => 41 01 ff 77",
    "ff ff ff 41 00 => 41 00 ff 77",
    f"ff ff ff 53 => 53 {status} 00 00 00 00 01",
]
for slot_byte in ("00", "10", "20"):
    for block in range(64):
        data = figure[block * 16:(block + 1) * 16].hex(" ")
        lines.append(f"ff ff ff 51 {slot_byte} {block:02x} => 51 10 {block:02x} {data}")
out.write_text("\n".join(lines) + "\n", encoding="ascii")
print(f"{out}: {len(lines)} lines")
