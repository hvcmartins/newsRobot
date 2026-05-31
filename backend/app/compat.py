"""
Compatibility patches for Python version differences.
Must be imported before any affected libraries (feedparser, etc.).
"""
import re
import html.parser

# feedparser 6.0.x does `from html.parser import tagfind_tolerant` which
# was removed in Python 3.13. Restore it if missing.
if not hasattr(html.parser, 'tagfind_tolerant'):
    html.parser.tagfind_tolerant = re.compile(
        r'([a-zA-Z][-.a-zA-Z0-9:_]*)(?:\s|/(?!>))*'
    )
if not hasattr(html.parser, 'attrfind_tolerant'):
    html.parser.attrfind_tolerant = re.compile(
        r'((?<=[\'"\s/])[^\s/>][^\s/=>]*)(\s*=+\s*'
        r'(\'[^\']*\'|"[^"]*"|(?![\'"])[^>\s]*))?(?:\s|/(?!>))*',
        re.VERBOSE,
    )
