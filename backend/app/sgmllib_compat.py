"""
Install as sgmllib.py into site-packages for Python 3.11+ compatibility.
Run: python -c "import sgmllib_compat; sgmllib_compat.install()"
or use the Dockerfile RUN command.
"""
import importlib.util
import site
import sys
import os

_STUB = '''"""sgmllib stub for Python 3.x where sgmllib was removed from stdlib."""
import html.parser, re

class SGMLParseError(Exception): pass

entityref    = re.compile(r"&(?P<ref>[a-zA-Z][-.a-zA-Z0-9]*)[^a-zA-Z0-9]")
incomplete   = re.compile(r"&[a-zA-Z#]")
interesting  = re.compile(r"[&<]")
shorttag     = re.compile(r"<(?P<name>[a-zA-Z][-.a-zA-Z0-9]*/)")
shorttagopen = re.compile(r"<[a-zA-Z][-.a-zA-Z0-9]*/")
starttagopen = re.compile(r"<[>a-zA-Z]")

class SGMLParser(html.parser.HTMLParser):
    def __init__(self, verbose=0):
        super().__init__(convert_charrefs=False)
    def unknown_starttag(self, tag, attrs): pass
    def unknown_endtag(self, tag): pass
'''


def install():
    if importlib.util.find_spec("sgmllib"):
        return
    dirs = site.getsitepackages()
    for d in dirs:
        target = os.path.join(d, "sgmllib.py")
        try:
            with open(target, "w") as f:
                f.write(_STUB)
            print(f"Installed sgmllib stub at {target}")
            return
        except PermissionError:
            continue
    print("Could not install sgmllib stub", file=sys.stderr)
