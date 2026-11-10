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
4. **The other games.** Spyro's Adventure 3DS (rated Bad: what goes wrong), Swap Force 3DS and
   SuperChargers Racing (rated Great), Trap Team 3DS (won't boot: why). The owner can dump the
   other three from his own 3DS.
5. **A picture for a monitor.** Both screens in one window: the top screen large and the touch
   screen beside or over it (Azahar's layouts are the start), the mouse as the touch screen, a
   controller layout like the console games', the portal menu (skylanders-portal's) for putting
   figures on.
6. **Core of Light.** A tab "Xbox 360 | 3DS" at the top; the 3DS games set up from the player's own
   dumps (decrypted CCI/CIA), their settings and figures as for the console games.

Open: the emulator fork's home (a private mirror of azahar-emu/azahar with our branch, since a
GitHub fork of a public repository can't be private), and how the figure library shows 3DS
progress (the 3DS games keep their own saves, not on the figure).
