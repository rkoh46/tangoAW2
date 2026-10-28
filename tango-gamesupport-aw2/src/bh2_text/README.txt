BH2 Campaign dialogue files (read by src/bh2_text.rs, checked by tools/bh2text/lint.py; the BH Campaign format, see ../bh_text/README.txt)

A scene:      == m14_pre
              == m02_pre | STURM, VON BOLT      (the COs the player may lead in that scene; default: the whole roster)
A row (box):  SPEAKER: first line / second line
              SPEAKER(h): ...   happy face     SPEAKER(s): ...   sad face
              Box = up to two lines of at most 176 pixels (about 26 to 33 characters) in AW2's font.
              {p} is a pause inside a line.
Speakers:     ASUKA (Black Hole's lead commander, Sonja after the prologue), ARIA (Nell's twin sister), KLAUS, AURELIA, CASSIUS, LIVIA (Emerald Sun, the secret mission), LEGIONARY,
              STURM, VON BOLT, HAWKE, KOAL, KINDLE, JUGGER, FLAK, LASH, ADDER, CLONE (Clone Andy), SONJA, CRUMB CO (Crumb as a CO),
              ANDY, NELL, MAX, OLAF, SAMI, GRIT, KANBEI, EAGLE, DRAKE, HACHI, COLIN, JESS, SENSEI, GRIMM, JAVIER, SASHA, JAKE, RACHEL,
              NARRATION (a box with no speaker), CRUMB / MORTAR / WICK / SOLDIER (the Black Hole trooper's face; the lines say who talks),
              SOLDIER OS / BM / GE / YC (a soldier of another colour),
              [CO]  the CO the player leads        [CO2]  the player's tag partner
Groups:       @IF STURM, HAWKE       rows shown only when the player leads Sturm or Hawke ([CO] inside means that CO)
              @OTHER                 rows shown to every CO of the pool that no @IF of the scene names ([CO] = that CO)
              @WITH HAWKE            rows shown when Hawke is in the player's pair (lead or partner)
              @PARTNER HAWKE         rows shown when the player's tag partner is Hawke ([CO2] inside means Hawke)
              @BOND HAWKE, KOAL      rows shown when the bond of Hawke / Koal / ... (their recruitment bond) is earned (the epilogue's toasts)
              @WITHOUT CLONE ANDY    rows shown when that CO is NOT in the player's pair ([CO] and [CO2] are the pair's lead and partner; one CO only)
              @END                   back to rows everybody sees
              [CO] outside a group is said, for each CO of the pool, by that CO.
Runs of boxes by one speaker are merged into one text by the compiler and equal texts share an id (budget: 3,072 text ids).
Songs:        @SONG name (campaign_music NAMED roles, aw2:<id>, co:<name>) or own:door / own:credits / own:aria, BH2's three songs (branches bh2music, aria; bh2_text.rs OWN_SONGS holds
              temporary stand-ins until they are merged). Every scene has one except the mid-battle ones (mNN_dayN, mNN_in_*), which keep the battle's music.
Files:        story (prologue), act1..act5 (the missions, M1-M31 in the final numbering), ending (epilogue, secret mission M32), credits (the staff roll: == HEADING [| secret], then rows of 21 characters).
Pools:        the scenes of a free pick name the pool in the header: ASUKA, CRUMB CO, HAWKE, KOAL, KINDLE, JUGGER, FLAK, LASH, ADDER, VON BOLT, CLONE ANDY (Sturm is a pick only in M5, which is forced).
