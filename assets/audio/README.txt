DIE AGAIN: TROLL — AUDIO ASSETS
================================

Drop sound files into the two subfolders below. The game auto-detects them
on next launch. If a file is missing, the corresponding event plays
silently — no crash, no error. You can add files one by one.

Supported formats (priority order):
  .ogg   (recommended — small, royalty-free, loops cleanly)
  .wav   (uncompressed; biggest files but lowest CPU)
  .mp3   (works but slightly slower to load; not recommended for SFX)

================================
sfx/ — short one-shot effects
================================
Each file should be a single short sound (50ms – 2s).
Filename must match EXACTLY (lowercase, no spaces).

  jump.ogg            player presses Space / jump button — short "boing"
  death.ogg           player dies (any cause) — splat / 8-bit explosion
  victory.ogg         player reaches the real portal — uplifting chime
  fake_portal.ogg     player touches a decoy portal — wrong-answer buzzer
  spike_reveal.ogg    hidden spike pops up nearby — sharp "shing"
  spike_drop.ogg      ceiling spike begins its fall — descending whoosh
  block_appear.ogg    invisible block becomes solid — solid thud
  crumble.ogg         fake floor crumbles under the player — wood breaking
  crusher.ogg         crusher block slams down — heavy metal thump
  click.ogg           UI button click — soft tactile click

Optional (game still works without these):
  land.ogg            player lands from a jump
  hover.ogg           cursor hovers over a UI button (use very quiet!)

================================
music/ — looping background tracks
================================
Music files should loop cleanly. Aim for 1-3 minutes; pygame loops them
seamlessly via the music channel.

  menu.ogg            main menu, settings, mode select, level select
  play.ogg            normal-mode gameplay
  nightmare.ogg       nightmare-mode gameplay (optional — falls back to play.ogg)

================================
Where to find free assets
================================
  https://freesound.org/        — huge SFX library, free for personal use
  https://opengameart.org/      — game art + audio, mostly CC-licensed
  https://kenney.nl/assets      — clean, royalty-free game asset packs
  https://patrickdearteaga.com/ — chiptune / arcade music tracks

================================
Volume control
================================
Master / Music / SFX sliders in Settings adjust real-time. The slider
values (0..100) are persisted in save.dat under "settings".
