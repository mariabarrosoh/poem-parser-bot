# utils/llm_utils.py
import os
import json
import re
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

def load_prompt(path: str) -> str:
    """
    Loads a prompt file from disk.

    Args:
        path (str): Path to the prompt file.

    Returns:
        str: Prompt text.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception as e:
        raise RuntimeError(f"Failed to read prompt file: {e}")


def parse_json_from_response(content: str) -> str:
    """
    Clean the model's response by removing Markdown code block delimiters to extract pure JSON string.

    Args:
        content (str): Raw response text from the model.

    Returns:
        str: Cleaned JSON string without Markdown backticks.
    """
    # Remove ```json ... ``` blocks
    cleaned = re.sub(r"```json\s*([\s\S]*?)\s*```", r"\1", content, flags=re.IGNORECASE).strip()

    # Remove any remaining ``` ... ``` blocks
    if cleaned.startswith("```") and cleaned.endswith("```"):
        cleaned = cleaned[3:-3].strip()

    # Escape chars markdown
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    cleaned = re.sub(f'([{re.escape(escape_chars)}])', r'\1', cleaned)

    return cleaned

def call_extractor(encoded_images: list, request_id: str) -> str:
    """
    Calls the LLM to extract HTML from base64-encoded poem images.

    Args:
        encoded_images (list): List of base64-encoded image strings.
        request_id (str): Unique request identifier.

    Returns:
        str: HTML content extracted from the images.
    """
    api_key = os.environ.get("GROQ_API_KEY")
    model_name = os.environ.get("MODEL_NAME")

    if not api_key:
        raise RuntimeError(f"{request_id} | GROQ_API_KEY not set.")
    if not model_name:
        raise RuntimeError(f"{request_id} | MODEL_NAME not set.")

    try:
        image_blocks = [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img}"}} for img in encoded_images]
        prompt = load_prompt("prompts/html_extractor.txt")

        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {
                    "role": "user",
                    "content": [{"type": "text", "text": prompt}] + image_blocks,
                }
            ],
            max_completion_tokens=2048,
            temperature=0,
            stream=False,
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        raise RuntimeError(f"{request_id} | Error during LLM extraction call: {e}")


def call_validator(encoded_images: list, raw_html: str, request_id: str) -> str:
    """
    Calls a second LLM to validate and correct the extracted HTML based on the original images.

    Args:
        encoded_images (list): List of base64-encoded image strings.
        raw_html (str): HTML output from the first LLM extraction.
        request_id (str): Unique request identifier.

    Returns:
        str: Corrected HTML, or "NO CHANGES" if the original is accurate.
    """
    api_key = os.environ.get("GROQ_API_KEY")
    model_name = os.environ.get("MODEL_NAME")

    if not api_key or not model_name:
        raise RuntimeError(f"{request_id} | Missing GROQ_API_KEY or MODEL_NAME")

    try:
        image_blocks = [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img}"}} for img in encoded_images]
        prompt = load_prompt("prompts/html_validator.txt")

        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {
                    "role": "user",
                    "content": (
                        [{"type": "text", "text": prompt}]
                        + [{"type": "text", "text": f"HTML to validate:\n{raw_html}"}]
                        + image_blocks
                    ),
                }
            ],
            max_completion_tokens=2048,
            temperature=0,
            stream=False,
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        raise RuntimeError(f"{request_id} | HTML validation failed: {e}")

def call_title_md_extractor(raw_html: str, request_id: str):
    """
    Extract the poem title and Markdown representation from the validated HTML using the LLM.

    Args:
        raw_html (str): Validated HTML content of the poem.
        request_id (str): Unique request identifier.

    Returns:
        tuple: (title (str), markdown_text (str)) extracted from the HTML.
               Returns (None, None) if extraction fails or response is invalid.
    """
    api_key = os.environ.get("GROQ_API_KEY")
    model_name = os.environ.get("MODEL_NAME")

    if not api_key or not model_name:
        raise RuntimeError(f"{request_id} | Missing GROQ_API_KEY or MODEL_NAME")

    try:
        prompt = load_prompt("prompts/title_md_extractor.txt")

        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {
                    "role": "user",
                    "content": (
                        [{"type": "text", "text": prompt}]
                        + [{"type": "text", "text": f"HTML:\n{raw_html}"}]
                    ),
                }
            ],
            max_completion_tokens=2048,
            temperature=0,
            stream=False,
        )

        content = response.choices[0].message.content.strip()

        try:
            clean_content = parse_json_from_response(content)
            parsed = json.loads(clean_content)
        except json.JSONDecodeError:
            return None, None

        title = parsed.get("title", "").strip()
        markdown = parsed.get("markdown", "").strip()

        return title, markdown

    except Exception as e:
        raise RuntimeError(f"{request_id} | Markdown/title extraction failed: {e}")
