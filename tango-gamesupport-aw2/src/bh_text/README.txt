BH Campaign dialogue files (read by src/bh_text.rs, checked by tools/bhtext/lint.py)

A scene:      == m14_pre
              == m02_pre | STURM, VON BOLT      (the COs the player may lead in that scene; default: the whole roster)
A row (box):  SPEAKER: first line / second line
              SPEAKER(h): ...   happy face     SPEAKER(s): ...   sad face
              Box = up to two lines of at most 176 pixels (about 26 to 33 characters) in AW2's font.
              {p} is a pause inside a line.
Speakers:     STURM, VON BOLT, HAWKE, KOAL, KINDLE, JUGGER, FLAK, LASH, ADDER, CLONE (Clone Andy), SONJA, CRUMB CO (Crumb as a CO),
              ANDY, NELL, MAX, OLAF, SAMI, GRIT, KANBEI, EAGLE, DRAKE, HACHI, COLIN, JESS, SENSEI, GRIMM, JAVIER, SASHA, JAKE, RACHEL,
              NARRATION (a box with no speaker), CRUMB / MORTAR / WICK / SOLDIER (the Black Hole trooper's face; the lines say who talks),
              SOLDIER OS / BM / GE / YC (a soldier of another colour),
              [CO]  the CO the player leads        [CO2]  the player's tag partner
Groups:       @IF STURM, HAWKE       rows shown only when the player leads Sturm or Hawke ([CO] inside means that CO)
              @OTHER                 rows shown to every CO of the pool that no @IF of the scene names ([CO] = that CO)
              @WITH HAWKE            rows shown when Hawke is in the player's pair (lead or partner)
              @PARTNER HAWKE         rows shown when the player's tag partner is Hawke ([CO2] inside means Hawke)
              @END                   back to rows everybody sees
              [CO] outside a group is said, for each CO of the pool, by that CO.
Runs of boxes by one speaker are merged into one text by the compiler and equal texts share an id (budget: 3,072 text ids).
