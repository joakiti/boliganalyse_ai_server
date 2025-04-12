import logging
import json
from typing import Dict, Any, Optional, List
from bs4 import BeautifulSoup

from .base_provider import BaseProvider, HtmlParseResult
from src.app.lib import html_utils # Import the new html_utils

logger = logging.getLogger(__name__)

class JsonLdProvider(BaseProvider):
    """Provider that extracts data from JSON-LD scripts within HTML."""

    @property
    def name(self) -> str:
        return "JSON-LD Provider"

    def can_handle(self, url: str, html_content: Optional[str] = None) -> bool:
        """Checks if the HTML content contains JSON-LD script tags."""
        if not html_content:
            return False
        try:
            soup = BeautifulSoup(html_content, 'lxml')
            json_ld_scripts = soup.find_all('script', type='application/ld+json')
            return len(json_ld_scripts) > 0
        except Exception as error:
            logger.error("Error checking for JSON-LD scripts", exc_info=error)
            return False

    async def extract_image_url(self, html_content: str) -> Optional[str]:
        """
        Extracts image URL, prioritizing JSON-LD, then meta tags, then generic extraction.
        """
        if not html_content:
            return None

        try:
            soup = BeautifulSoup(html_content, 'lxml')

            # 1. Check JSON-LD scripts
            json_ld_scripts = soup.find_all('script', type='application/ld+json')
            for script in json_ld_scripts:
                try:
                    if script.string:
                        data = json.loads(script.string)
                        items = data if isinstance(data, list) else [data]
                        for item in items:
                            # Look for common image properties in JSON-LD schemas
                            if isinstance(item, dict):
                                image = item.get('image')
                                if isinstance(image, str) and image.startswith('http'):
                                    logger.debug("Found image URL in JSON-LD 'image' property.")
                                    return image
                                if isinstance(image, list) and len(image) > 0 and isinstance(image[0], str) and image[0].startswith('http'):
                                     logger.debug("Found image URL in JSON-LD 'image' list.")
                                     return image[0]
                                # Check nested structures common in Product/Offer schemas
                                offers = item.get('offers')
                                if isinstance(offers, dict) and isinstance(offers.get('itemOffered'), dict):
                                    nested_image = offers['itemOffered'].get('image')
                                    if isinstance(nested_image, str) and nested_image.startswith('http'):
                                        logger.debug("Found image URL in nested JSON-LD 'offers.itemOffered.image'.")
                                        return nested_image
                except json.JSONDecodeError:
                    logger.warning("Failed to parse JSON-LD content in script tag.")
                except Exception as e:
                     logger.error(f"Error processing JSON-LD script content: {e}", exc_info=True)


            # 2. Fallback to meta tags (using html_utils)
            logger.debug("No suitable image in JSON-LD, checking meta tags and generic extraction.")
            meta_image = await html_utils.extract_first_image_url(html_content)
            if meta_image:
                return meta_image

            return None # No image found

        except Exception as error:
            logger.error("Failed to extract image URL in JsonLdProvider", exc_info=error)
            return None

    async def parse_html(self, url: str, html_content: str) -> HtmlParseResult:
        """
        Parses HTML, extracts JSON-LD, combines it with general text content.
        """
        logger.info(f"Parsing HTML with JsonLdProvider for URL: {url}")
        extracted_json_ld_list: List[Dict[str, Any]] = []
        property_image_url: Optional[str] = None
        extracted_text: str = ""

        try:
            # Extract image URL first (uses JSON-LD priority)
            property_image_url = await self.extract_image_url(html_content)

            # Extract general text content
            extracted_text = await html_utils.extract_text_from_html(html_content)

            # Extract and combine all JSON-LD data
            soup = BeautifulSoup(html_content, 'lxml')
            json_ld_scripts = soup.find_all('script', type='application/ld+json')
            for script in json_ld_scripts:
                 try:
                     if script.string:
                         data = json.loads(script.string)
                         # Add to list whether it's a single object or a list itself
                         if isinstance(data, list):
                             extracted_json_ld_list.extend(data)
                         else:
                             extracted_json_ld_list.append(data)
                 except json.JSONDecodeError:
                     logger.warning("Failed to parse JSON-LD content in script tag during main parse.")
                 except Exception as e:
                     logger.error(f"Error processing JSON-LD script content during main parse: {e}", exc_info=True)

            # Combine JSON-LD with extracted text for AI analysis context
            # Convert JSON-LD list to a string representation
            json_ld_string = json.dumps(extracted_json_ld_list, indent=2, ensure_ascii=False)
            combined_text = f"JSON-LD Data:\n{json_ld_string}\n\nExtracted Page Text:\n{extracted_text}"

            return {
                "originalLink": url, # JSON-LD sites are usually the direct source
                "property_image_url": property_image_url,
                "extractedText": combined_text,
                "json_ld_data": extracted_json_ld_list # Optionally return raw JSON-LD
            }

        except Exception as error:
            logger.error(f"Failed to parse HTML with JsonLdProvider for {url}", exc_info=error)
            # Return None values for data fields to match TS returning {}
            return {
                "originalLink": None,
                "property_image_url": None,
                "extractedText": None,
                "json_ld_data": None
            }