"""
Utility Functions Module
"""

import re
from typing import List


def markdown_to_html(md_text: str) -> str:
    """
    Convert Markdown-formatted text to HTML.

    Supports:
    - Headings (#, ##, ...)
    - Blockquotes (>)
    - Paragraphs with line breaks
    - Bold (**text** or __text__)
    - Italic (*text* or _text_)

    Args:
        md_text (str): Markdown text.

    Returns:
        str: HTML string.
    """
    html_lines: List[str] = []
    buffer: List[str] = []  # Used to group paragraph lines

    def flush_buffer():
        """Append the current paragraph buffer to HTML output."""
        if buffer:
            paragraph = '<br>'.join(buffer)
            html_lines.append(f"<p>{paragraph}</p>")
            buffer.clear()

    for line in md_text.split('\n'):
        stripped = line.lstrip()
        leading_spaces = len(line) - len(stripped)
        spaces_html = '&nbsp;' * leading_spaces
        content = spaces_html + stripped

        # Headings (#, ##, ...)
        if re.match(r'^(#{1,6})\s+(.*)', stripped):
            flush_buffer()
            match = re.match(r'^(#{1,6})\s+(.*)', stripped)
            level = len(match.group(1))
            content = spaces_html + match.group(2)
            html_lines.append(f"<h{level}>{content}</h{level}>")

        # Blockquote
        elif stripped.startswith('>'):
            flush_buffer()
            quote_content = stripped[1:].strip()
            html_lines.append(f"<blockquote>{quote_content}</blockquote>")

        # Normal text → add to paragraph buffer
        else:
            buffer.append(content)

    flush_buffer()

    # Apply bold and italic formatting
    html = '\n'.join(html_lines)
    html = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html)
    html = re.sub(r'__(.*?)__', r'<strong>\1</strong>', html)
    html = re.sub(r'\*(.*?)\*', r'<em>\1</em>', html)
    html = re.sub(r'_(.*?)_', r'<em>\1</em>', html)

    return html
