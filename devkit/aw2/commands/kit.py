"""aw2dev kit: keep the devkit growing with the game. new-command / new-skill create skeletons; check lists docs, skills and tests that point at
things that do not exist (commands, files, scenarios)."""
import re, sys
from pathlib import Path
from .. import cfg, util

TEMPLATE_COMMAND = '''"""aw2dev {name}: TODO one line on what it does (docs/dev/{name}.md)."""
from .. import cfg, util


def register(sub):
    p = sub.add_parser("{name}", help="TODO one-line help")
    p.add_argument("--example", help="TODO")
    p.set_defaults(fn=run)


def run(args):
    util.say("{name}: not implemented yet")
    return 0   # exit code: 0 pass, 1 fail
'''
TEMPLATE_SKILL = """---
name: {name}
description: TODO one sentence: what this skill does and when to use it (the model reads this to decide)
---

1. TODO the steps, each calling `./aw2dev ...` (build, the scenario or checker, the audit).
2. Look at the pictures (`./aw2dev sheet latest ...`); a checker pass alone is not proof.
3. Add or update the regression test in the suite (devkit/CONTRIBUTING-KIT.md) and the docs/dev entry.
"""
TEMPLATE_DOC = """# {name}

TODO what it is, where the code is (file and function), how to run it (`aw2dev ...`), what pass means, known limits.
"""


def register(sub):
    k = sub.add_parser("kit", help="grow the devkit: new-command, new-skill, check (devkit/CONTRIBUTING-KIT.md)")
    ks = k.add_subparsers(dest="kitcmd", required=True)
    a = ks.add_parser("new-command", help="skeleton devkit/aw2/commands/<name>.py + docs/dev/<name>.md")
    a.add_argument("name")
    a.set_defaults(fn=new_command)
    a = ks.add_parser("new-skill", help="skeleton .claude/skills/<name>/SKILL.md")
    a.add_argument("name")
    a.set_defaults(fn=new_skill)
    a = ks.add_parser("check", help="list docs/skills/tests that reference missing commands or files")
    a.add_argument("--strict", action="store_true", help="warnings fail too")
    a.set_defaults(fn=check)


def _write(path, text):
    if path.exists():
        util.say("exists, left alone:", path.relative_to(cfg.REPO))
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    util.say("created", path.relative_to(cfg.REPO))


def new_command(a):
    name = a.name.strip().lower()
    if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
        util.die("command names are lowercase letters, digits and _")
    _write(cfg.DEVKIT / "aw2" / "commands" / f"{name}.py", TEMPLATE_COMMAND.format(name=name))
    _write(cfg.REPO / "docs" / "dev" / f"{name}.md", TEMPLATE_DOC.format(name=name))
    print("next: fill both in, add a regression test (suite entry / scenario / checker), a skill (`aw2dev kit new-skill`), then `aw2dev kit check`.")
    return 0


def new_skill(a):
    name = a.name.strip().lower()
    if not re.fullmatch(r"[a-z][a-z0-9-]*", name):
        util.die("skill names are lowercase letters, digits and -")
    _write(cfg.REPO / ".claude" / "skills" / name / "SKILL.md", TEMPLATE_SKILL.format(name=name))
    return 0


OPTIONAL = {"devkit/config.local.toml", "devkit/release_allow.txt"}
PATH_RE = re.compile(r"`((?:devkit|docs/dev|tools|tango-gamesupport-aw2|tango|tango-session|tango-match|tango-net|\.claude/skills)/[A-Za-z0-9_./\-*<>]+)`")
CMD_RE = re.compile(r"aw2dev ([a-z][a-z0-9-]*)(?: ([a-z][a-z0-9-]*))?")


def _subcommands():
    from .. import cli
    p = cli.build_parser()
    import argparse
    top = next(x for x in p._actions if isinstance(x, argparse._SubParsersAction))
    out = {}
    for name, sp in top.choices.items():
        subs = {}
        for x in sp._actions:
            if isinstance(x, argparse._SubParsersAction):
                subs = set(x.choices)
        out[name] = subs
    return out


def check(a):
    errors, warns = [], []
    cmds = _subcommands()
    files = [cfg.REPO / "CLAUDE.md", cfg.DEVKIT / "README.md", cfg.DEVKIT / "CONTRIBUTING-KIT.md"] + sorted((cfg.REPO / "docs" / "dev").glob("*.md")) + \
        sorted((cfg.REPO / ".claude" / "skills").glob("*/SKILL.md"))
    from .. import scenarios
    for f in files:
        if not f.exists():
            continue
        text = f.read_text()
        rel = f.relative_to(cfg.REPO)
        spans = "\n".join(re.findall(r"`([^`\n]+)`", text))        # (only commands written as code count; prose may say "aw2dev refuses")
        for m in CMD_RE.finditer(spans):
            c, sc = m.group(1), m.group(2)
            if c not in cmds:
                errors.append(f"{rel}: `aw2dev {c}` is not a command")
            elif cmds[c] and sc and sc not in cmds[c] and sc not in ("--help",) and c in ("net", "kit", "audit"):
                errors.append(f"{rel}: `aw2dev {c} {sc}` is not a sub-command of {c} ({', '.join(sorted(cmds[c]))})")
        for m in PATH_RE.finditer(text):
            p = m.group(1).rstrip(".,")
            if any(ch in p for ch in "*<>") or p.startswith("devkit/work") or p in OPTIONAL or f.name in ("decomp.md", "CONTRIBUTING-KIT.md"):
                continue                  # (globs, run output, optional local files, and paths that live in the decomposition repo)
            if not (cfg.REPO / p).exists():
                errors.append(f"{rel}: missing file {p}")
        if f.name == "SKILL.md":
            fm = re.match(r"---\nname: (.+)\ndescription: (.+)\n---", text)
            if not fm:
                errors.append(f"{rel}: frontmatter must be `name:` and `description:`")
            elif fm.group(1).strip() != f.parent.name:
                errors.append(f"{rel}: name {fm.group(1)} != folder {f.parent.name}")
            if "TODO: kit not built yet" in text:
                warns.append(f"{rel}: placeholder skill")
            elif "TODO" in text:
                warns.append(f"{rel}: still has TODO text")
    # every command should have a docs/dev mention and a skill mention
    docs = "\n".join(p.read_text() for p in (cfg.REPO / "docs" / "dev").glob("*.md"))
    skills = "\n".join(p.read_text() for p in (cfg.REPO / ".claude" / "skills").glob("*/SKILL.md"))
    for c in cmds:
        if f"aw2dev {c}" not in docs:
            warns.append(f"command `{c}` is not mentioned in docs/dev")
        if f"aw2dev {c}" not in skills and c not in ("profiles", "runs", "kit", "clean"):
            warns.append(f"command `{c}` is not mentioned in any skill")
    # modules in commands/ that did not register
    for m in sorted((cfg.DEVKIT / "aw2" / "commands").glob("*.py")):
        if m.name.startswith("_"):
            continue
        if m.stem not in cmds and f'add_parser("{m.stem}"' not in m.read_text():
            errors.append(f"commands/{m.name} does not register a `{m.stem}` subcommand")
    # scenarios in docs must exist
    for f in files:
        if f.exists():
            for sc in ([] if f.name == "CONTRIBUTING-KIT.md" else re.findall(r"aw2dev live ([a-z0-9][a-z0-9-]*)", f.read_text())):
                if sc not in scenarios.SCEN and sc not in ("lobby", "unranked", "browse", "rules-lobby", "rules-unranked", "solo", "rejoin", "ios-gate", "<scenario>", "--list"):
                    errors.append(f"{f.relative_to(cfg.REPO)}: unknown live scenario {sc}")
    for w in warns:
        print("  [warn]", w)
    for e in errors:
        print("  [FAIL]", e)
    util.say(f"kit check: {len(errors)} error(s), {len(warns)} warning(s)")
    return 1 if errors or (a.strict and warns) else 0
