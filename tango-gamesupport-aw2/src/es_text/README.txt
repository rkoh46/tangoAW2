Emerald Sun Campaign dialogue files (read by src/es_text.rs, checked by tools/estext/lint.py; voices: tools/estext/BIBLE.md)

A scene:      == m14_pre
              == m02_pre | KLAUS, LIVIA         (the COs the player may lead in that scene; default: the whole roster)
A row (box):  SPEAKER: first line / second line
              SPEAKER(h): ...   happy face     SPEAKER(s): ...   sad face
              Box = up to two lines of at most 176 pixels (about 26 to 33 characters) in AW2's font.
              {p} is a pause inside a line.
Speakers:     KLAUS, AURELIA, CASSIUS, LIVIA, VARRO, JESS, EAGLE, DRAKE, JAVIER, GRIMM, SENSEI, KANBEI, SONJA, COLIN, SASHA, OLAF, GRIT, MAX, JAKE, SAMI, NELL, ANDY, HACHI, RACHEL,
              ADDER, FLAK, KINDLE, KOAL, LASH, NARRATION (a box with no speaker), LEGIONARY (an Emerald Sun soldier), SOLDIER (a Black Hole trooper's face),
              SOLDIER OS / BM / GE / YC / BH (a soldier of another colour),
              [CO]  the CO the player leads        [CO2]  the player's tag partner
Groups:       @IF KLAUS, LIVIA       rows shown only when the player leads Klaus or Livia ([CO] inside means that CO)
              @OTHER                 rows shown to every CO of the pool that no @IF of the scene names ([CO] = that CO)
              @WITH CASSIUS          rows shown when Cassius is in the player's pair (lead or partner)
              @PARTNER CASSIUS       rows shown when the player's tag partner is Cassius ([CO2] inside means Cassius)
              @WITHOUT AURELIA       rows shown when that CO is NOT in the player's pair ([CO] and [CO2] are the pair's lead and partner; one CO only)
              @END                   back to rows everybody sees
              [CO] outside a group is said, for each CO of the pool, by that CO.
@SONG role             the scene's song (once a scene): a role name (aw2dev sound list), aw2:<id> or co:<name>
Runs of boxes by one speaker are merged into one text by the compiler and equal texts share an id (budget: 3,072 text ids).
