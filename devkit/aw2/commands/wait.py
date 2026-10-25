"""aw2dev wait: wait for a process to end, or a file to appear / hold a text (docs/dev/testing.md "Waiting for a long run").

  wait PID                  until process PID has ended
  wait FILE                 until FILE exists and is not empty
  wait FILE --text MARK     until FILE contains MARK (a run's "passed in", a done-marker line)
  options: --timeout S (default 3 h; exit 1 when it runs out), --poll S (default 10)

Do not wait with `until ! pgrep -f "run.py ..."; do sleep ..; done`: `pgrep -f` matches the waiting shell's own command line (it contains the same words), so the loop never
ends and piles up. Start the long run with its output in a file, keep its PID (`$!`), and wait on the PID or on the text its last line has (`aw2dev wait /tmp/run.log --text "passed in"`).
"""
import os, time
from pathlib import Path


def register(sub):
    p = sub.add_parser("wait", help="wait for a PID to end, or a file to appear / contain a text (never `until ! pgrep -f ...`)")
    p.add_argument("target", help="a PID, or a file")
    p.add_argument("--text", help="with a file: until it contains this text")
    p.add_argument("--timeout", type=float, default=3 * 3600, help="seconds (default 3 h)")
    p.add_argument("--poll", type=float, default=10, help="seconds between looks (default 10)")
    p.set_defaults(fn=run)


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def done(target, text=None):
    """Whether what `target` names has happened: a PID gone, a file there (with `text` in it)."""
    if target.isdigit() and text is None:
        return not alive(int(target))
    p = Path(target)
    if not p.exists() or p.stat().st_size == 0:
        return False
    if text is None:
        return True
    try:
        return text in p.read_text(errors="ignore")
    except OSError:
        return False


def run(args):
    t0 = time.time()
    while not done(args.target, args.text):
        if time.time() - t0 > args.timeout:
            print(f"aw2dev wait: {args.target}: not done after {args.timeout:.0f} s")
            return 1
        time.sleep(args.poll)
    print(f"aw2dev wait: {args.target}: done after {time.time() - t0:.0f} s")
    return 0
