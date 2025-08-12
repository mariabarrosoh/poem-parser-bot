"""
Utility Functions Module
"""

import base64
import re
from typing import List


def encode_image_to_base64(image_path: str, request_id: str) -> str:
    """
    Encode an image file to Base64 format.

    Args:
        image_path (str): Path to the image file.
        request_id (str): Unique request identifier (used for error logging).

    Returns:
        str: Base64-encoded string of the image content.

    Raises:
        ValueError: If the file extension is not supported.
        RuntimeError: If the file is missing or cannot be read.
    """
    if not image_path.lower().endswith((".jpg", ".jpeg", ".png")):
        raise ValueError(f"{request_id} | Only .jpg, .jpeg, or .png images are supported.")

    try:
        with open(image_path, "rb") as image_file:
            image_bytes = image_file.read()
            return base64.b64encode(image_bytes).decode("utf-8")
    except FileNotFoundError:
        raise RuntimeError(f"{request_id} | Image file not found: {image_path}")
    except Exception as e:
        raise RuntimeError(f"{request_id} | Failed to encode image: {e}")


def escape_markdown(content: str) -> str:
    """
    Escape Markdown formatting characters in a string.

    Args:
        content (str): Text to escape.

    Returns:
        str: Cleaned text with Markdown characters escaped.
    """
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', content).strip()


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
