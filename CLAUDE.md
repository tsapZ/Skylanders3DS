# CLAUDE.md: Skylanders3DS

The rules every Skylanders repository follows (tests only on copies of the owner's data, git and
GitHub, shared code, releases) are in Core of Light's maintainer/RULES.md
(https://github.com/tsapZ/SkylandersCoreOfLight/blob/main/maintainer/RULES.md):

@../../SkylandersCoreOfLight/SkylandersCoreOfLight/maintainer/RULES.md

## Goal

The five Nintendo 3DS Skylanders games on PC through an emulator core (Azahar, GPLv2+) with a
3DS Portal of Power over emulated infrared, started from Core of Light (tab "Xbox 360 | 3DS").
Private and planning only for now (owner's word, 2026-11-10): README, docs/findings-*.md,
docs/plan.md, tools/.

## Particular to this repository

- The owner's 3DS dumps (decrypted CCI) stay where he put them; never copied in here, never in an
  issue. Screenshots of a run stay in %LOCALAPPDATA%\SkylandersDev\runs\3ds.
- A scripted run uses a portable Azahar (its `user` folder next to azahar.exe), never %APPDATA%\Azahar,
  muted, and gets input only through tools/azahar_taps.ps1 (posted to Azahar's window).
- Close Azahar through its window at the end of a run (the log is written out on close).
- One game at a time, and none while a Xbox 360 port's timed A/B runs.
