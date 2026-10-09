# Crumb's art

`crumb_user.png`: Crumb art by the tangoAW2 author (rkoh), original (not from
any game; GPL-3.0-or-later like the code). A side-view trooper, mirrored to
look left as the game's figures are stored; 104x118, 14 colours and
transparency, 4-bit indexed; used as Crumb's CO page, power and tag screen
figure. `tools/crumb_art/reconstruct.py` made it from the author's upscaled
picture (grid detection, sampling, palette snapping); a native-size PNG
takes the same path (`python3 tools/crumb_art/reconstruct.py in.png
tango-gamesupport-aw2/art/crumb/crumb_user.png --flip`) or can replace the
file as it is.
