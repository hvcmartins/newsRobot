"""
Compatibility patches — must be imported before feedparser is used anywhere.

feedparser/sgml.py copies method bytecodes from sgmllib.SGMLParser into its
own class so they execute in feedparser.sgml's global scope.  Those methods
(ultimately html.parser.HTMLParser.goahead / handle_starttag) reference
tagfind_tolerant and attrfind_tolerant, which were:
  • present in html.parser globals in Python < 3.13
  • removed from html.parser in Python 3.13

The NameError: name 'tagfind_tolerant' is not defined is raised because the
copied functions look in feedparser.sgml.__dict__, not html.parser.__dict__.
Fix: inject both names into every scope that might need them.
"""
import re
import html.parser

_tagfind_tolerant = re.compile(r'([a-zA-Z][-.a-zA-Z0-9:_]*)(?:\s|/(?!>))*')
_attrfind_tolerant = re.compile(
    r'((?<=[\'"\s/])[^\s/>][^\s/=>]*)(\s*=+\s*'
    r'(\'[^\']*\'|"[^"]*"|(?![\'"])[^>\s]*))?(?:\s|/(?!>))*',
    re.VERBOSE,
)

# 1. Patch html.parser module globals (Python 3.13+)
if not hasattr(html.parser, 'tagfind_tolerant'):
    html.parser.tagfind_tolerant = _tagfind_tolerant
if not hasattr(html.parser, 'attrfind_tolerant'):
    html.parser.attrfind_tolerant = _attrfind_tolerant

# 2. Patch feedparser.sgml globals — the copied bytecodes execute here,
#    so this is the scope where the names must exist at call time.
try:
    import feedparser.sgml as _fp_sgml
    if not hasattr(_fp_sgml, 'tagfind_tolerant'):
        _fp_sgml.tagfind_tolerant = _tagfind_tolerant
    if not hasattr(_fp_sgml, 'attrfind_tolerant'):
        _fp_sgml.attrfind_tolerant = _attrfind_tolerant
except Exception:
    pass
