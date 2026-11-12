# Skylanders 3DS (private, planning)

The five Nintendo 3DS Skylanders games on PC: Spyro's Adventure, Giants, Swap Force, Trap Team and
SuperChargers Racing. Each is its own game (n-Space and Beenox), not a port of the console ones.
There is no static recompiler for the 3DS like ReXGlue is for the Xbox 360, so the plan is an
emulator core with what the games need added to it, started from Core of Light (a tab
"Xbox 360 | 3DS" at the top).

Nothing of the games is in this repository: no ROMs, no screenshots, no artwork.

## Where it stands (2026-11-12)

- **Giants 3DS is playable with figures** in Azahar (the merge of Lime3DS and Citra, GPLv2 or later)
  with this repository's patch (`emulator/apply_portal_patch.py`): `AutoConnection` connects an
  emulated infrared portal that answers the game as a console portal does; the game takes the
  figures into its crystals and plays.
- The protocol: every infrared packet is the portal light's colour (r g b) and then a console portal
  command (R, A, C, S, Q, W); the game asks for the status (S) itself.
- In the patched Azahar: File > Skylanders Portal > Place figure... puts a figure file on the portal
  (the 1024-byte files of Documents\Skylanders\Figures; the file is never written), Lift figure off
  takes it away. Scripted runs name figure files in `SKYLANDERS_PORTAL_FIGURE` (separated by `;`).
- **Swap Force and Trap Team 3DS are playable with figures** too: they speak the same portal
  protocol as Giants and play with the same emulated portal, unchanged.
- Trap Team 3DS stopped at once in every Azahar ("Won't boot"): it runs an ARM-mode CPS, which
  Azahar's CPU core can't translate; `emulator/apply_cps_nop.py` makes it a no-op, as the CPU does
  in user mode. SuperChargers Racing 3DS runs to its driver select without asking for the portal
  yet; Spyro's Adventure 3DS to its language screen.

Details: [docs/findings-2026-11-10.md](docs/findings-2026-11-10.md),
[docs/findings-2026-11-11.md](docs/findings-2026-11-11.md),
[docs/findings-2026-11-12.md](docs/findings-2026-11-12.md). Plan: [docs/plan.md](docs/plan.md).

## Tools

- `tools/azahar_probe.ps1`: starts a game in a portable Azahar (muted, no update check), saves its
  window every few seconds and its log.
- `tools/azahar_taps.ps1`: the same with taps and key presses posted to Azahar's window, so a
  scripted run gets past menus without the real mouse or keyboard.
- `tools/ir_log_summary.py`: what a game and the emulated portal said to each other in one run
  (commands and counts, blocks read and written, light colours, the first packets with replies).
- `tools/make_blank_figure.py`: an empty figure file of a toy (as skylanders-portal makes them), for
  tests without anyone's own figures; `tools/make_reply_table.py`: a reply table for experiments
  (`SKYLANDERS_PORTAL_REPLIES`).

## License

The emulator part will be a fork of Azahar and so GPLv2 or later. The portal and figure code comes
from tsapZ/skylanders-portal (MIT), which a GPL program may include.

Not affiliated with Activision, Nintendo or the Azahar project. Skylanders is a trademark of its
owners.
