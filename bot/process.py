"""
Poem Processing Module

This module processes one or more poem images to extract, validate,
and retrieve metadata such as the poem's title and text content
using a combination of OCR and large language model (LLM) based tools.
"""

from dotenv import load_dotenv
from bot.utils.llm_utils import call_extractor
from bot.utils.utils import encode_image_to_base64


load_dotenv()


def process_poem(image_paths: list[str]) -> dict[str, str]:
    """
    Process a list of poem images to extract the poem's title and text content.

    Args:
        image_paths (list[str]): List of file paths to poem images.

    Returns:
        dict[str, str]: Dictionary containing 'poem_title' and 'poem_text'.
    """
    if not image_paths:
        return {"poem_title": "", "poem_text": ""}

    # Encode all images as base64 strings
    encoded_images = [
        encode_image_to_base64(path.strip()) for path in image_paths
    ]

    # Extract title and markdown poem text from the encoded images
    poem_title, poem_text = call_extractor(encoded_images)

    return {"poem_title": poem_title, "poem_text": poem_text}


if __name__ == "__main__":

    paths = ["poems/junin.jpeg"]
    result = process_poem(paths)
    print(result)
