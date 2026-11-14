#!/usr/bin/env python3
"""Subset the Material Symbols font to the icons the portals actually use.

    scripts/icons.py          rewrite the font <link> in both index.html files
    scripts/icons.py --check  exit 1 if an index.html is missing an icon (CI)

The full variable font is ~1.1 MB; the subset is a few KB, which matters on mobile data.
Icons are found in templates/TS: <span class="icon ...">name</span>, icon: 'name', and
'name' literals in ternaries inside .icon spans.
"""
import pathlib, re, sys, urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
APPS = ["fundi-pro", "jenga-pro"]
SPAN = re.compile(r'class="[^"]*\b(?:icon|material-symbols-outlined)\b[^"]*"[^>]*>\s*([^<]+?)\s*<', re.S)
PROP = re.compile(r"""[iI]con\s*:\s*['"]([a-z0-9_]+)['"]""")
WORD = re.compile(r"""['"]([a-z][a-z0-9_]{2,})['"]""")

def scan():
    names = set()
    files = [p for app in APPS for p in (ROOT / "frontend" / app / "src" / "app").rglob("*") if p.suffix in (".html", ".ts")]
    files += list((ROOT / "frontend" / "design-system").rglob("*.html")) + list((ROOT / "frontend" / "design-system").rglob("*.ts"))
    for p in files:
        text = p.read_text(errors="ignore")
        for m in SPAN.finditer(text):
            body = m.group(1)
            if "{{" in body:  # {{ cond ? 'a' : 'b' }}
                names.update(WORD.findall(body))
            elif re.fullmatch(r"[a-z0-9_]+", body):
                names.add(body)
        names.update(PROP.findall(text))
    return sorted(n for n in names if not n.isdigit())

def url(names):
    q = "family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400..600,0..1,0&icon_names=" + ",".join(names) + "&display=block"
    return "https://fonts.googleapis.com/css2?" + q

LINK = re.compile(r'<link rel="stylesheet" href="https://fonts\.googleapis\.com/css2\?family=Material\+Symbols\+Outlined[^"]*">')

def main():
    names = scan(); want = f'<link rel="stylesheet" href="{url(names)}">'
    bad = 0
    for app in APPS:
        p = ROOT / "frontend" / app / "src" / "index.html"; s = p.read_text()
        if not LINK.search(s):
            print(f"{p}: Material Symbols <link> not found"); bad = 1; continue
        if "--check" in sys.argv:
            if want not in s:
                print(f"{app}: icon font subset is out of date - run scripts/icons.py"); bad = 1
        else:
            p.write_text(LINK.sub(want, s))
    if not bad:
        print(f"{len(names)} icons" + (" - subset up to date" if "--check" in sys.argv else " - index.html updated"))
    return bad

if __name__ == "__main__":
    sys.exit(main())
