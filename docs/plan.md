# Plan

Each step ends with something that can be tried; the next one only starts when it works.

1. **Build Azahar from source** (Windows, MSVC), unchanged, and check it runs Giants 3DS like the
   official build.
2. **AutoConnection connects a portal device.** A new `IRDevice` (the 3DS portal) that only logs:
   `AutoConnection` connects it as `RequireConnection` connects the Circle Pad Pro. The log then
   shows what the game sends first. Questions this answers: is it the console portal's command set
   (R, A, S, Q, W, C ...) inside the infrared packets, or something else; does the game expect the
   device to speak first; how often it polls.
3. **The portal answers.** If the commands are the console ones, the portal device hands them to
   skylanders-portal's `SoftwarePortal` and sends its replies back; figures from the same figure
   files the Xbox 360 ports use (Documents\Skylanders\Figures). If not, the protocol gets written
   down here first, from the game's traffic.
   **Reached in its first form, 2026-11-11** (docs/findings-2026-11-11.md): the commands are the console
   ones behind the light's colour; the device answers them itself, as SoftwarePortal does, from figure
   files; Giants 3DS took two of them into its crystals and went into play. Still to do: the real
   SoftwarePortal (linked, figures from the figure folder, writes saved), a way to swap figures while
   playing (a menu or a hotkey instead of the list), what the high nibble in Q means, W (writes).
4. **The other games.** Spyro's Adventure 3DS (rated Bad: what goes wrong), Swap Force 3DS and
   SuperChargers Racing (rated Great), Trap Team 3DS (won't boot: why). The owner can dump the
   other three from his own 3DS.
   **Swap Force and Trap Team reached, 2026-11-12** (docs/findings-2026-11-12.md): both talk to the
   portal exactly as Giants does and play with the same device; Trap Team needed an ARM-mode CPS as a
   no-op (emulator/apply_cps_nop.py). Still to do: SuperChargers Racing (to its driver select, no
   portal call yet: what brings it in, and vehicles), Spyro's Adventure past its language screen,
   traps in Trap Team.
   **All five reached, 2026-11-12 06:00:**
   - Spyro's Adventure plays with figures after emulator/apply_irnop_patch.py (its older infrared
     library's ReceiveIrnop).
   - SuperChargers Racing races: a driver through the tab above its driver select, then a vehicle
     put on while it asks (07:35).

   Still to do: traps in Trap Team.
5. **A picture for a monitor.** Both screens in one window: the top screen large and the touch
   screen beside or over it (Azahar's layouts are the start), the mouse as the touch screen, a
   controller layout like the console games', the portal menu (skylanders-portal's) for putting
   figures on. From CoL #72 (a player's ideas): a key that switches the layout (both, swapped, only
   one), the touch screen on a second monitor; later perhaps a phone or tablet as the touch screen.

   Azahar has most of it built in: layouts 0-6 (default: top over touch; single screen; large screen
   with the touch screen small beside it; side by side; separate windows, for a second monitor;
   hybrid; custom), F10 to the next, F8 upright, the mouse as the touch screen, our File > Skylanders
   Portal menu. Pictures of all of them with Swap Force 3DS (2026-11-12): single screen is out (the
   games ask to tap the touch screen, e.g. an element), default and side by side leave much of a 16:9
   monitor empty. **The default for a 16:9 monitor: large screen (layout_option 2), the touch screen
   bottom right (small_screen_position 2) at proportion 2.5** instead of Azahar's 4, so its buttons
   are big enough to hit with the mouse (a top screen about 3.6x the 3DS's 400x240 on a 1920x1080
   window, the touch screen about 1.5x). The scripted runs keep layout 0 (tools/azahar_taps.ps1 sets
   it: the tap positions are measured there).
6. **Core of Light.** A tab "Xbox 360 | 3DS" at the top; the 3DS games set up from the player's own
   dumps (decrypted CCI/CIA), their settings and figures as for the console games.
   - **Recognising a dump**, as tools/code_services.py reads it:
     - the file must start with "NCSD" at 0x100;
     - partition 0 is an NCCH with NoCrypto set. An encrypted dump gets the line "decrypt it on your
       own 3DS first".
     - The product code at NCCH 0x150 (`CTR-P-` and four letters) names the game; the fourth letter
       is the region (P Europe, E America; others when they turn up).

     | Code | Game |
     |---|---|
     | ASP | Spyro's Adventure |
     | AG6 | Giants |
     | BSF | Swap Force |
     | BS9 | Trap Team |
     | BL5 | SuperChargers Racing |

     The owner's European dumps also give the program ids 000400000004C000, 00040000000A3500,
     00040000000E7F00, 000400000013BE00 and 000400000016AE00. CIA files (content 0 is the same NCCH)
     come after CCI.
   - **The emulator:**
     - Core of Light downloads a release of the Azahar fork into its own folder, portable (the `user`
       folder next to azahar.exe), and never touches %APPDATA%\Azahar.
     - A release of a GPL program needs its source in public. So the fork goes public when the tab
       does; that's the owner's decision, not before.
   - **Per game:**
     - a card as for the console games;
     - settings: screen layout, resolution scale, the portal;
     - figures from the same library (Documents\Skylanders\Figures), put on through the emulator's
       Skylanders Portal menu;
     - saves in the portable folder, backed up the way the console saves are.
   - **First thing to try:** the tab lists the dumps it finds in a folder the player picks, with the
     game's name and region, and starts one in the portable Azahar.

Open: the emulator fork's home (a private mirror of azahar-emu/azahar with our branch, since a
GitHub fork of a public repository can't be private), and how the figure library shows 3DS
progress (the 3DS games keep their own saves, not on the figure).
