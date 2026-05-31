"""
Compatibility patches applied before feedparser is imported anywhere.

Python 3.13 removed tagfind_tolerant and attrfind_tolerant from html.parser.
feedparser 6.x references these names in function bytecode copied from
HTMLParser, so the NameError surfaces at parse time rather than import time.

We force all feedparser submodules to load, then inject both names into
every loaded feedparser module's __dict__ and into html.parser's __dict__.
"""
import re
import sys
import html.parser

_tagfind_tolerant = re.compile(r'([a-zA-Z][-.a-zA-Z0-9:_]*)(?:\s|/(?!>))*')
_attrfind_tolerant = re.compile(
    r'((?<=[\'"\s/])[^\s/>][^\s/=>]*)(\s*=+\s*'
    r'(\'[^\']*\'|"[^"]*"|(?![\'"])[^>\s]*))?(?:\s|/(?!>))*',
    re.VERBOSE,
)

# Patch html.parser module globals
if not hasattr(html.parser, 'tagfind_tolerant'):
    html.parser.tagfind_tolerant = _tagfind_tolerant
if not hasattr(html.parser, 'attrfind_tolerant'):
    html.parser.attrfind_tolerant = _attrfind_tolerant

# Import feedparser now so all its submodules are in sys.modules
try:
    import feedparser  # noqa: F401, E402
except Exception:
    pass

# Patch every loaded feedparser submodule's global namespace
for _modname, _mod in list(sys.modules.items()):
    if _modname.startswith('feedparser') and _mod is not None:
        try:
            if not hasattr(_mod, 'tagfind_tolerant'):
                _mod.tagfind_tolerant = _tagfind_tolerant
            if not hasattr(_mod, 'attrfind_tolerant'):
                _mod.attrfind_tolerant = _attrfind_tolerant
        except Exception:
            pass
