# Forking tangoAW2

You are welcome to fork tangoAW2 and build your own Advance Wars 2 mod on it. This page covers the rules that come with the code and the few things a fork must change so that it does not get mixed up with tangoAW2.

## The licence

tangoAW2 is **GPL-3.0-or-later**, like [Tango](https://github.com/tangobattle/tango), which it is built on. For a fork, that means:

- You may copy, change and share it, including releasing your own builds.
- Your fork stays GPL-3.0-or-later, and anyone who gets a build from you can get its source.
- Keep the copyright and licence notices, `LICENSE` and `CREDITS.md`, and add your own changes to the credits.
- Say that your fork is built on tangoAW2 (and Tango), and don't present it as tangoAW2 itself.

Original art and music in this repository are credited in `CREDITS.md`. Keep those credits with them if you use them.

## What a fork can't do

- **It is not a standalone game.** The engine runs the real Advance Wars 2 cartridge, so every player needs their own dump of the USA AW2 ROM, and the USA Dual Strike ROM for the Dual Strike content.
- **Never commit or distribute anything from the games.** That covers ROMs, saves, extracted graphics, maps, text or music notes. tangoAW2 reads all of it from the player's own ROMs at run time; keep it that way. The release check (`aw2dev release`, the `forbidden` and `allowed_dirs` lists in `devkit/config.toml`) is there to catch mistakes.
- **USA versions only.** Every address the code patches or reads is mapped for the USA builds of AW2 and Dual Strike. EU and JP would need all of them re-mapped.
- Advance Wars is a trademark of Nintendo. Keep the "not affiliated" line in your README.

## What to change first

These stop your players and tangoAW2's from meeting each other and keep your app from updating itself to tangoAW2's releases.

| What | Where | Why |
|---|---|---|
| Update source | `tango/src/updater.rs` (`GITHUB_RELEASES_URL` and the releases link) | Otherwise your app offers tangoAW2's builds as updates. |
| Issue links | `.github/ISSUE_TEMPLATE/config.yml`, README | Bug reports should reach you. |
| Online rooms and lobby | `tango-lobby/src/room.rs` (`tangoaw2-room-`), `tango-gamesupport-aw2/src/online.rs`, `tango-lobby/src/browse.rs` (`TAG`), `tango-lobby/src/unranked.rs` (`tangoaw2-unranked-`) | Use your own prefix so your rooms, lobbies and Unranked pool are separate from tangoAW2's. |
| Simulation version | `tango-backend-mgba/src/shared.rs` (`SHARED_SIM_VERSION`) | Give your fork its own base value; builds with different simulations then refuse to play each other instead of desyncing. Bump `inspect::SIM_VERSION` (`tango-gamesupport-aw2/src/inspect.rs`) whenever your rules change. |
| App name and data folder | `tango/src/config.rs` (`DATA_DIR_NAME`), `macos/Info.plist.mako` (`CFBundleIdentifier`), `ios/bundle.py` (`BUNDLE_ID`) | Your app keeps its own settings, saves and ROM folder, and can be installed beside tangoAW2. |
| Title-screen badge and version | `tango/Cargo.toml` | Players can tell the two apart. |

After the rename, run the whole test set (`./aw2dev test`) and an online check (`./aw2dev net repeat`) before your first release.

## Building your own content

Everything tangoAW2 adds was built with its dev kit, and the kit comes with the fork:

- `./aw2dev --help` lists the tools: build, tests, maps (gen, lint, render-check), campaigns, COs (portrait import, verify, balance), army skins, music (compose, render, similar) and releases.
- `docs/dev/README.md` is the index of the developer docs: how campaigns, maps, COs, armies, music and online play work, with the rules the checks enforce.
- `CLAUDE.md` describes the repository for AI coding agents.

Questions about how something works are welcome in tangoAW2's [Issues](https://github.com/rkoh46/tangoAW2/issues).
