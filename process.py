# process.py
import re
from dotenv import load_dotenv
from utils.llm_utils import call_extractor, call_validator, call_title_md_extractor
from utils.utils import encode_image_to_base64
from utils.logging_config import configure_logger

load_dotenv()

logger = configure_logger("PoemParserProcessor")

def empty_html(raw_html: str) -> bool:
    """
    Checks if the given raw HTML corresponds to an empty poem output.

    Args:
        raw_html (str): The raw HTML string to check.

    Returns:
        bool: True if the HTML is considered empty (no poem content), False otherwise.
    """
    normalized = re.sub(r"\s+", "", raw_html).lower()
    empty_template = '<!doctypehtml><htmllang="es"><head><metacharset="utf-8"></head><body></body></html>'
    return normalized == empty_template


def process(image_paths: list, request_id: str):
    """
    Processes a poem from one or more image paths by extracting and validating HTML.

    Args:
        image_paths (list): List of paths to images containing the poem.
        request_id (str): Unique identifier for the request.

    Returns:
        dict: Dictionary with request_id and the final HTML content.
    """
    if not image_paths:
        logger.warning(f"{request_id} | No image paths provided.")
        return None, None, None

    try:
        encoded_images = [encode_image_to_base64(path.strip(), request_id) for path in image_paths]
        raw_html = call_extractor(encoded_images, request_id)
        if not raw_html or empty_html(raw_html):
            logger.warning(f"{request_id} | The input is not a valid poem")
            return None, None, None

        validated_html = call_validator(encoded_images, raw_html, request_id)

        if validated_html.strip().upper() == "NO CHANGES":
            logger.info(f"{request_id} | HTML is valid. No corrections needed.")
            output_html = raw_html
        else:
            logger.info(f"{request_id} | HTML corrected by validator.")
            output_html = validated_html

        title, markdown_text = call_title_md_extractor(output_html, request_id)
        if not title:
            logger.warning(f"{request_id} | Poem title not extracted.")
        if not markdown_text:
            logger.warning(f"{request_id} | Poem text not extracted.")

        logger.info(f"{request_id} | Poem processed successfully.")
        return title, output_html, markdown_text

    except Exception as e:
        logger.error(f"{request_id} | Failed to process poem: {e}")
        raise


if __name__ == "__main__":
    import os
    import uuid

    image_paths = ["test/input/junin.jpeg"]
    output_folder = "test/output"

    try:
        request_id = uuid.uuid4().hex[:16]
        poem_title, poem_html, poem_md = process(image_paths, request_id)
        if not poem_title:
            print(f"{request_id} | No poem title extracted.")
        else:
            print("Title: ", poem_title)

        if not poem_md:
            print(f"{request_id} | No poem text extracted.")
        else:
            print("Poem: ", poem_md)

        if not poem_html:
            print(f"{request_id} | No poem HTML extracted.")
        else:
            file_path = os.path.join(output_folder, f"{request_id}.html")
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(poem_html)
            print(f"Poem saved to {file_path}")

    except Exception as e:
        print(f"Error: {e}")
