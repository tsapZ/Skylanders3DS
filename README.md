# Skylanders 3DS (private, planning)

The five Nintendo 3DS Skylanders games on PC: Spyro's Adventure, Giants, Swap Force, Trap Team and
SuperChargers Racing. Each is its own game (n-Space and Beenox), not a port of the console ones.
There is no static recompiler for the 3DS like ReXGlue is for the Xbox 360, so the plan is an
emulator core with what the games need added to it, started from Core of Light (a tab
"Xbox 360 | 3DS" at the top).

Nothing of the games is in this repository: no ROMs, no screenshots, no artwork.

## Where it stands (2026-11-10)

- Azahar (the merge of Lime3DS and Citra, GPLv2 or later) runs Spyro's Adventure 3DS and Giants 3DS
  at full speed (60 FPS) up to the point where the game wants the portal.
- Giants 3DS then opens the infrared service ir:USER and calls `AutoConnection`, which Azahar
  doesn't implement, so the game waits at "Aim at the PORTAL OF POWER".
- Azahar already has the pieces for an infrared device (the Circle Pad Pro is one): the portal can
  be another, connected through `AutoConnection`.

Details: [docs/findings-2026-11-10.md](docs/findings-2026-11-10.md). Plan: [docs/plan.md](docs/plan.md).

## Tools

- `tools/azahar_probe.ps1`: starts a game in a portable Azahar (muted, no update check), saves its
  window every few seconds and its log.
- `tools/azahar_taps.ps1`: the same with taps and key presses posted to Azahar's window, so a
  scripted run gets past menus without the real mouse or keyboard.

## License

The emulator part will be a fork of Azahar and so GPLv2 or later. The portal and figure code comes
from tsapZ/skylanders-portal (MIT), which a GPL program may include.

Not affiliated with Activision, Nintendo or the Azahar project. Skylanders is a trademark of its
owners.
