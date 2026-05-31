"""
Compatibility patches applied before feedparser is imported anywhere.

Python 3.x removed several names from html.parser that feedparser 6.x
references via function bytecode copied from HTMLParser.  Because the
bytecode executes in feedparser's own module scope, the NameErrors surface
at parse time rather than import time.

Names injected into every feedparser submodule and html.parser:
  tagfind_tolerant   – removed from html.parser in Python 3.13
  attrfind_tolerant  – removed from html.parser in Python 3.13
  unescape           – was html.parser.unescape (removed in Python 3.9),
                       now lives at html.unescape
"""
import html
import re
import sys
import html.parser

_tagfind_tolerant = re.compile(r'([a-zA-Z][-.a-zA-Z0-9:_]*)(?:\s|/(?!>))*')
_attrfind_tolerant = re.compile(
    r'((?<=[\'"\s/])[^\s/>][^\s/=>]*)(\s*=+\s*'
    r'(\'[^\']*\'|"[^"]*"|(?![\'"])[^>\s]*))?(?:\s|/(?!>))*',
    re.VERBOSE,
)
_unescape = html.unescape

# Patch html.parser module globals
if not hasattr(html.parser, 'tagfind_tolerant'):
    html.parser.tagfind_tolerant = _tagfind_tolerant
if not hasattr(html.parser, 'attrfind_tolerant'):
    html.parser.attrfind_tolerant = _attrfind_tolerant
if not hasattr(html.parser, 'unescape'):
    html.parser.unescape = _unescape

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
            if not hasattr(_mod, 'unescape'):
                _mod.unescape = _unescape
        except Exception:
            pass
