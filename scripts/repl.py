"""
Clipboard pre-processor for pasting LaTeX-like content into Mobius.

Run this script before pasting content into the Mobius question editor.
It reads the current clipboard, applies the transformations below, and
writes the result back to the clipboard ready to paste:

  - Remove line comments (# ...)
  - Escape backslashes and double-quotes for JSON embedding
  - Strip newlines and collapse whitespace
  - Convert inline math ($...$) to Nobius LaTeX notation \\(...\\)
"""

import re

import pyperclip

replacements = [
    (r"\#.*?\n", ""),
    (r'\\', r'\\\\'),
    (r"\"", r'\\"'),
    (r"\n\#.*?\n", ""),
    (r"\r\n", ""),
    (r"\ +", " "),
    (r'\$(.*?)\$', r'\\\(\1\\\)')
]

a = pyperclip.paste()
for pattern, repl in replacements:
    a = re.sub(pattern, repl, a)
pyperclip.copy(a)
print(a)
