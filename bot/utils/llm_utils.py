"""
LLM Utilities for Poem Extraction and Validation

This module provides helper functions to interact with the Groq API to extract
poem metadata from encoded images using large language models (LLMs).
"""

import os
import json
import re
from typing import Optional, Tuple, List
from groq import Groq
from dotenv import load_dotenv

load_dotenv()


def load_prompt(path: str) -> str:
    """
    Load the content of a prompt file from disk.

    Args:
        path (str): File path to the prompt file.

    Returns:
        str: The prompt content as a stripped string.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception as e:
        raise RuntimeError(f"Failed to read prompt file: {e}") from e


def parse_json_from_response(content: str) -> str:
    """
    Extract JSON string from LLM's response by removing Markdown code block
    delimiters.

    Args:
        content (str): Raw response string from the model.

    Returns:
        str: Cleaned JSON string ready for parsing.
    """
    # Remove fenced code blocks with json syntax
    cleaned = re.sub(r"```json\s*([\s\S]*?)\s*```", r"\1", content,
                     flags=re.IGNORECASE).strip()

    # Remove any remaining fenced code blocks (without language specifier)
    if cleaned.startswith("```") and cleaned.endswith("```"):
        cleaned = cleaned[3:-3].strip()

    return cleaned


def call_extractor(
        encoded_images: List[str]) -> Optional[Tuple[str, str]]:
    """
    Call the Groq API to extract poem metadata (title and markdown text)
    from base64-encoded images.

    Args:
        encoded_images (List[str]): List of base64-encoded images.

    Returns:
        Optional[Tuple[str, str]]: A tuple of (title, markdown text) if
                                   extraction succeeds, otherwise (None, None).
    """
    api_key = os.environ.get("GROQ_API_KEY")
    model_name = os.environ.get("MODEL_NAME")

    if not api_key:
        raise RuntimeError("GROQ_API_KEY not set.")
    if not model_name:
        raise RuntimeError("MODEL_NAME not set.")

    try:
        # Prepare image blocks in the format expected by the Groq API
        image_blocks = [
            {"type": "image_url",
             "image_url": {"url": f"data:image/jpeg;base64,{img}"}}
            for img in encoded_images
        ]

        # Load prompt text from disk
        prompt = load_prompt("prompts/poem_extractor.txt")

        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt}
                        ] + image_blocks,
                }
            ],
            max_completion_tokens=2048,
            temperature=0,
            stream=False,
        )

        # Extract and clean the response content
        content = response.choices[0].message.content.strip()
        clean_content = parse_json_from_response(content)

        # Parse JSON content
        parsed = json.loads(clean_content)

        title = parsed.get("title", "").strip()
        markdown = parsed.get("markdown", "").strip()

        return title, markdown

    except json.JSONDecodeError:
        # Return None if JSON parsing fails
        return None, None
    except Exception as e:
        raise RuntimeError(
            f"Poem extraction failed: {e}") from e
