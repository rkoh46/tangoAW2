#!/usr/bin/env python3
"""One-off: list the scene sites of the BH acts and dump their current lines as rows (baseline for the rewrite)."""
import re, sys, json
SRC = "/Users/danielc/tangoAW2-bhdialog/tango-gamesupport-aw2/src/"
NAMES = {"STURM":"STURM","VON_BOLT":"VON BOLT","HAWKE":"HAWKE","KOAL":"KOAL","KINDLE":"KINDLE","JUGGER":"JUGGER","FLAK":"FLAK","LASH":"LASH","ADDER":"ADDER","CLONE_ANDY":"CLONE","SONJA":"SONJA","CRUMB":"CRUMB CO"}
def coname(x):
    return NAMES.get(x, x)
def parse_str(s, i):
    # s[i] == '"'
    j = i + 1; out = []
    while s[j] != '"':
        if s[j] == '\\':
            n = s[j+1]
            out.append({'n':'\n','r':'\r','"':'"','\\':'\\',"'":"'"}.get(n, n)); j += 2
        else:
            out.append(s[j]); j += 1
    return ''.join(out), j + 1
def balanced(s, i, o, c):
    d = 0; j = i; instr = False
    while True:
        ch = s[j]
        if instr:
            if ch == '\\': j += 2; continue
            if ch == '"': instr = False
        else:
            if ch == '"': instr = True
            elif ch == o: d += 1
            elif ch == c:
                d -= 1
                if d == 0: return j
        j += 1
def split_top(s):
    parts = []; d = 0; cur = []; instr = False; j = 0
    while j < len(s):
        ch = s[j]
        if instr:
            cur.append(ch)
            if ch == '\\': cur.append(s[j+1]); j += 2; continue
            if ch == '"': instr = False
        else:
            if ch == '"': instr = True; cur.append(ch)
            elif ch in '([{': d += 1; cur.append(ch)
            elif ch in ')]}': d -= 1; cur.append(ch)
            elif ch == ',' and d == 0: parts.append(''.join(cur)); cur = []
            else: cur.append(ch)
        j += 1
    if ''.join(cur).strip(): parts.append(''.join(cur))
    return [p.strip() for p in parts if p.strip()]
def element_row(e):
    m = re.match(r'(say|sad|happy|troop)\((.*)\)((?:\.\w+\([^)]*\))*)$', e, re.S)
    if not m: return None
    kind, args, mods = m.groups()
    if kind == 'troop':
        who = 'CRUMB'; text = args.strip()
    else:
        mm = re.match(r'co::(\w+)\s*,\s*(.*)$', args, re.S)
        if not mm: return None
        who = coname(mm.group(1)); text = mm.group(2).strip()
        if kind == 'sad': who += '(s)'
        if kind == 'happy': who += '(h)'
    if not text.startswith('"'): return None
    t, end = parse_str(text, 0)
    if text[end:].strip(): return None
    gates = re.findall(r'\.(only|with|only_partner)\(co::(\w+)\)', mods)
    return who, t.replace('\r', ' / ').replace('\n', ' '), gates

def rows_of_vec(body):
    """body: inside vec![ ... ]. Returns (rows, complex_elements)."""
    rows = []; bad = []
    for e in split_top(body):
        e = re.sub(r'//[^\n]*', '', e).strip()
        if not e: continue
        r = element_row(e)
        if r is None: bad.append(e)
        else: rows.append(r)
    return rows, bad

def fmt_rows(rows, pool_note=''):
    out = []; cur = None
    def flush_gate(g):
        pass
    for who, text, gates in rows:
        g = tuple(gates)
        if g != cur:
            if cur: out.append('@END')
            if g:
                kind, c = g[0]
                d = {'only':'IF','with':'WITH','only_partner':'PARTNER'}[kind]
                out.append(f'@{d} {coname(c)}')
            cur = g
        out.append(f'{who}: {text}')
    if cur: out.append('@END')
    return out

def sites(path):
    s = open(path).read()
    res = []
    for m in re.finditer(r'\bScene::new\(|(?<![\w:])scene\(', s):
        i = m.end() - 1
        if s[max(0, m.start()-3):m.start()] == 'fn ' : continue
        j = balanced(s, i, '(', ')')
        arg = s[i+1:j]
        line = s.count('\n', 0, m.start()) + 1
        # context
        fn = None
        for fm in re.finditer(r'^fn (bh\d+)\(', s[:m.start()], re.M): fn = fm.group(1)
        before = s[max(0, m.start()-200):m.start()]
        res.append(dict(file=path.split('/')[-1], line=line, start=m.start(), end=j+1, fn=fn, arg=arg, before=before))
    return res
if __name__ == '__main__':
    for f in sys.argv[1:]:
        for st in sites(SRC + f):
            a = st['arg'].strip()
            kind = 'lit' if a.startswith('vec![') and balanced(a, 3, '[', ']') == len(a) - 1 else 'complex'
            tail = st['before'][-70:].replace('\n', ' ')
            print(f"{st['file']}:{st['line']} {st['fn']} {kind} :: ...{tail} || {a[:60]!r}")

def slot_of(st):
    b = st['before'][-160:]
    if re.search(r'm\.intro\s*=\s*$', b): return 'pre'
    if re.search(r'm\.victory\s*=\s*$', b): return 'post'
    if re.search(r'm\.after\s*=\s*$', b): return 'map'
    if re.search(r'front2_victory\s*=\s*$', b): return 'front2_post'
    m = re.search(r'on_day\(\s*(\d+),[^;]*?$', b, re.S)
    if m and 'Action::Scene(' in b[m.start():]: return 'day' + m.group(1)
    m = re.search(r'Cond::Custom\((\w+)\)', b)
    if m: return 'when_' + m.group(1)
    return None
