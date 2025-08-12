"""
Poem Processing Module

This module processes one or more poem images to extract, validate,
and retrieve metadata such as the poem's title and text content
using a combination of OCR and large language model (LLM) based tools.
"""

import re
from dotenv import load_dotenv
from utils.llm_utils import call_extractor
from utils.utils import encode_image_to_base64
from utils.logging_config import configure_logger

# Load environment variables
load_dotenv()

# Initialize logger
logger = configure_logger("PoemParserProcessor")


def empty_html(raw_html: str) -> bool:
    """
    Determine whether a raw HTML string is effectively empty or contains
    no meaningful content based on a known empty template.

    Args:
        raw_html (str): The raw HTML string to inspect.

    Returns:
        bool: True if the HTML matches the empty template, False otherwise.
    """
    normalized = re.sub(r"\s+", "", raw_html).lower()
    empty_template = (
        '<!doctypehtml><htmllang="es"><head><metacharset="utf-8"></head><body></body></html>'
    )
    return normalized == empty_template


def process(image_paths: list[str], request_id: str) -> dict[str, str]:
    """
    Process a list of poem images to extract the poem's title and text content.

    Args:
        image_paths (list[str]): List of file paths to poem images.
        request_id (str): Unique identifier for the request, used in logging.

    Returns:
        dict[str, str]: Dictionary containing 'poem_title' and 'poem_text'.
    """
    if not image_paths:
        logger.warning(f"{request_id} | No image paths provided.")
        return {"poem_title": "", "poem_text": ""}

    try:
        # Encode all images as base64 strings
        encoded_images = [encode_image_to_base64(path.strip(), request_id) for path in image_paths]

        # Extract title and markdown poem text from the encoded images
        poem_title, poem_text = call_extractor(encoded_images, request_id)

        if not poem_title:
            logger.warning(f"{request_id} | Poem title not extracted.")
        if not poem_text:
            logger.warning(f"{request_id} | Poem text not extracted.")

        logger.info(f"{request_id} | Poem processed successfully.")
        return {"poem_title": poem_title, "poem_text": poem_text}

    except Exception as e:
        logger.error(f"{request_id} | Failed to process poem: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    """
    Example usage of the process function when running this script directly.
    Processes a hardcoded image path and prints the result.
    """

    import uuid

    image_paths = ["poems/input/junin.jpeg"]

    try:
        # Generate a short unique request ID for logging
        request_id = uuid.uuid4().hex[:16]

        # Process the poem images and print results
        result = process(image_paths, request_id)
        print(result)

    except Exception as error:
        print(f"Error: {error}")
