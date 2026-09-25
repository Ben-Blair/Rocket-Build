"""Minimal S-expression reader/writer for KiCad files + symbol 'extends' resolution."""
import re, os

SYMDIR = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols/"
FPDIR = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints/"

# Project-local footprints (fp-lib-table's ${KIPRJMOD}/RocketSenior.pretty), which
# is where "RocketSenior:..." resolves.  Searched before FPDIR so a local redraw
# always wins over a same-named stock part.
PRJDIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FP_SEARCH = [PRJDIR, FPDIR]


def fp_path(libfp):
    """lib:name -> .kicad_mod path, project-local library first."""
    lib, name = libfp.split(':', 1)
    for root in FP_SEARCH:
        p = os.path.join(root, lib + '.pretty', name + '.kicad_mod')
        if os.path.exists(p):
            return p
    raise IOError("no footprint %s in %s" % (libfp, FP_SEARCH))

TOKEN = re.compile(r'''\s*(?:("(?:[^"\\]|\\.)*")|(\()|(\))|([^\s()"]+))''')


def parse(text):
    """Return list of top-level nodes. Atoms are str; quoted strings are ('q', value)."""
    pos = 0
    stack = [[]]
    n = len(text)
    while pos < n:
        m = TOKEN.match(text, pos)
        if not m:
            break
        pos = m.end()
        q, op, cl, atom = m.groups()
        if op:
            new = []
            stack[-1].append(new)
            stack.append(new)
        elif cl:
            stack.pop()
        elif q is not None:
            stack[-1].append(('q', unquote(q)))
        else:
            stack[-1].append(atom)
    return stack[0]


def unquote(s):
    s = s[1:-1]
    return s.replace('\\"', '"').replace('\\\\', '\\').replace('\\n', '\n')


def quote(s):
    out = s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
    return '"%s"' % out


def dumps(node, indent=0):
    if isinstance(node, tuple):
        return quote(node[1])
    if isinstance(node, str):
        return node
    parts = [dumps(c, indent + 1) for c in node]
    one = '(' + ' '.join(parts) + ')'
    if len(one) <= 110 and '\n' not in one:
        return one
    pad = '\t' * (indent + 1)
    head = parts[0] if parts else ''
    body = ''.join('\n' + pad + p for p in parts[1:])
    return '(' + head + body + '\n' + '\t' * indent + ')'


def head(node):
    return node[0] if node and isinstance(node[0], str) else None


def find(node, name):
    for c in node:
        if isinstance(c, list) and head(c) == name:
            return c
    return None


def findall(node, name):
    return [c for c in node if isinstance(c, list) and head(c) == name]


def sval(node, name):
    c = find(node, name)
    if not c:
        return None
    v = c[1]
    return v[1] if isinstance(v, tuple) else v


_libcache = {}


def load_lib(lib):
    if lib not in _libcache:
        _libcache[lib] = parse(open(SYMDIR + lib + '.kicad_sym').read())[0]
    return _libcache[lib]


def get_symbol(lib, name):
    """Return a flattened symbol node (extends resolved)."""
    root = load_lib(lib)
    node = None
    for s in findall(root, 'symbol'):
        if isinstance(s[1], tuple) and s[1][1] == name:
            node = s
            break
    if node is None:
        raise KeyError('%s:%s' % (lib, name))
    ext = find(node, 'extends')
    if ext is None:
        return [c for c in node]
    parent = get_symbol(lib, ext[1][1])
    merged = [node[0], node[1]]
    own_props = {p[1][1] for p in findall(node, 'property')}
    # keep parent's non-property structure (graphics, pins, pin_names, etc.)
    for c in parent[2:]:
        if head(c) == 'property':
            if c[1][1] in own_props:
                continue
            merged.append(c)
        elif head(c) == 'symbol':
            # rename child graphic units  PARENT_0_1 -> NAME_0_1
            c = [x for x in c]
            unit = c[1][1]
            suffix = unit[len(ext[1][1]):]
            c[1] = ('q', name + suffix)
            merged.append(c)
        else:
            merged.append(c)
    for c in node[2:]:
        if head(c) != 'extends':
            merged.append(c)
    return merged


def pins(sym):
    """[(number, name, etype)] over all graphic units."""
    out = []
    for unit in findall(sym, 'symbol'):
        for p in findall(unit, 'pin'):
            out.append((sval(p, 'number'), sval(p, 'name'), p[1]))
    return out


def fp_pads(libfp):
    root = parse(open(fp_path(libfp)).read())[0]
    out = []
    for p in findall(root, 'pad'):
        n = p[1][1] if isinstance(p[1], tuple) else p[1]
        out.append(n)
    return out


if __name__ == '__main__':
    import sys
    for spec in sys.argv[1:]:
        lib, name = spec.split(':')
        s = get_symbol(lib, name)
        ps = pins(s)
        print('### %s  (%d pins)  footprint=%s' % (spec, len(ps), sval(
            [p for p in findall(s, 'property') if p[1][1] == 'Footprint'][0], 'x') or
            [p for p in findall(s, 'property') if p[1][1] == 'Footprint'][0][2][1]))
        def key(t):
            m = re.match(r'(\d+)', t[0] or '')
            return (0, int(m.group(1))) if m else (1, t[0] or '')
        for num, nm, et in sorted(ps, key=key):
            print('  %-4s %-22s %s' % (num, nm, et))
        print()
