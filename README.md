# Skylanders 3DS

The five Nintendo 3DS Skylanders games on PC with figures: Spyro's Adventure, Giants, Swap Force,
Trap Team and SuperChargers Racing. Each is its own game (n-Space and Beenox), not a port of the
console ones. There is no static recompiler for the 3DS like ReXGlue is for the Xbox 360, so this
is the Azahar emulator with an emulated 3DS Portal of Power added to it.

Nothing of the games is in this repository or the download: no ROMs, no screenshots, no artwork.

## Download and play

1. Get the zip from [tsapZ/azahar's releases](https://github.com/tsapZ/azahar/releases) (Windows,
   64-bit), unzip it anywhere and start `azahar.exe`. Its settings and saves stay in the `user`
   folder next to it, so an Azahar you already have is not touched.
2. Open a dump of your own cartridge (decrypted .cci/.3ds).
3. When the game asks for the portal: **File > Skylanders Portal > Place figure...** and pick a
   figure file (the 1024-byte dumps, for example from `Documents\Skylanders\Figures` of the Xbox 360
   ports). **Lift figure off** takes it off again. The file is only read: what the game writes to
   the figure is not saved, the 3DS games keep their progress in their own saves.
4. F10 switches between Azahar's screen layouts (View > Screen Layout has them too): on a 16:9
   monitor *Large Screen* fits well, the big top screen with the touch screen in a corner.

| Game | State |
|---|---|
| Spyro's Adventure 3DS | plays with figures |
| Giants 3DS | plays with figures |
| Swap Force 3DS | plays with figures |
| Trap Team 3DS | plays with figures (it didn't start in any Azahar before: a CPU fix, below) |
| SuperChargers Racing 3DS | races with a driver and a vehicle |

Problems and ideas go to [Core of Light's issues](https://github.com/tsapZ/SkylandersCoreOfLight/issues),
not to the Azahar team: this isn't an official Azahar build. Later Core of Light gets a
"Xbox 360 | 3DS" tab that finds your dumps and starts them in this Azahar.

## What was changed in Azahar

The source is the `skylanders` branch of [tsapZ/azahar](https://github.com/tsapZ/azahar/tree/skylanders)
(its last commits); `emulator/` here has the same changes as patch scripts for a plain Azahar checkout.

- **The portal over infrared** (`apply_portal_patch.py`): the games connect with `AutoConnection`;
  every packet is the portal light's colour (r g b) and then a console portal command (R, A, C, S,
  Q, W), so the emulated portal answers as a console portal does. Scripted runs name figure files
  in `SKYLANDERS_PORTAL_FIGURE` (separated by `;`).
- **Spyro's Adventure's older infrared library** takes each packet with `ReceiveIrnop`, which Azahar
  lacked (`apply_irnop_patch.py`, found with `tools/code_services.py`).
- **Trap Team 3DS** runs an ARM-mode CPS at boot, which Azahar's CPU core (dynarmic) couldn't
  translate, so the emulator stopped at once. In user mode CPS changes nothing, and dynarmic already
  treats the Thumb CPS as a no-op; `apply_cps_nop.py` does the same for ARM mode
  ([tsapZ/dynarmic](https://github.com/tsapZ/dynarmic/tree/skylanders)).

Details: [docs/findings-2026-11-10.md](docs/findings-2026-11-10.md),
[docs/findings-2026-11-11.md](docs/findings-2026-11-11.md),
[docs/findings-2026-11-12.md](docs/findings-2026-11-12.md). Plan: [docs/plan.md](docs/plan.md).

## Tools

- `tools/azahar_probe.ps1`: starts a game in a portable Azahar (muted, no update check), saves its
  window every few seconds and its log.
- `tools/azahar_taps.ps1`: the same with taps and key presses posted to Azahar's window (F-keys
  too, F10 the next layout), so a scripted run gets past menus without the real mouse or keyboard;
  it uses the default layout, which its tap positions are measured on.
- `tools/ir_log_summary.py`: what a game and the emulated portal said to each other in one run
  (commands and counts, blocks read and written, light colours, the first packets with replies).
- `tools/make_blank_figure.py`: an empty figure file of a toy (as skylanders-portal makes them), for
  tests without anyone's own figures; `tools/make_reply_table.py`: a reply table for experiments
  (`SKYLANDERS_PORTAL_REPLIES`).
- `tools/code_services.py`: what a decrypted dump asks for, without running it: the services its
  exheader allows and the infrared commands in its code (`--code-out` writes the decompressed code
  for a disassembler, into a local folder only).

## How it was made

To be upfront about it: almost all of the code and docs here and in the Azahar branch were written
by [Claude](https://claude.ai) in Claude Code. I decided what to build and tested it with my own
cartridges. If AI-made projects aren't your thing, that's fair.

## License

Azahar and so tsapZ/azahar are GPLv2 or later. The scripts and docs here are MIT, like the other
Skylanders repositories; the portal and figure code comes from tsapZ/skylanders-portal (MIT), which a
GPL program may include.

Not affiliated with Activision, Nintendo or the Azahar project. Skylanders is a trademark of its
owners.
