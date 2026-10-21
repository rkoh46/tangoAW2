---
name: aw2-release
description: Release tangoAW2: checklist, notes, IPA, tag and push. Use only when the user asks for a release; pushing needs their approval every time.
---

1. Confirm with the user: version, notes, and that new visuals were approved. Do NOT push or tag without their yes.
2. Write the release notes file (player-facing changelog; it becomes the tag message).
3. `./aw2dev release <ver> --notes notes.txt --dry-run` and fix every FAIL (branch hirestilt, clean tree, fast-forwards, no game files).
4. After approval: `./aw2dev release <ver> --notes notes.txt --yes` (bump, release-dist build, tests, install-mac, IPA to ~/Downloads, tag, push
   `hirestilt` + `HEAD:main/v030/aw2/ds-campaign2` + tag, watch workflow, rerun failed jobs once, list assets). Without `--yes` it stops before the push.
5. Check the assets: macOS dmg, Windows exe/pdb, Linux AppImage/debug, `tangoaw2-<ver>-ios.ipa`.
6. Tell the user to reopen the app (install-mac never closes a running one). Details: docs/dev/release.md.
