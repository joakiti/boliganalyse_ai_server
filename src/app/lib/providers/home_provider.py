import logging
from typing import Optional
from bs4 import BeautifulSoup

from .base_provider import BaseProvider, HtmlParseResult
from src.app.lib import html_utils # Import the html_utils
from src.app.lib.url_utils import extract_domain # Import url utils

logger = logging.getLogger(__name__)

class HomeProvider(BaseProvider):
    """Provider implementation for Home.dk."""

    @property
    def name(self) -> str:
        return "Home.dk"

    def can_handle(self, url: str, html_content: Optional[str] = None) -> bool:
        """Checks if the URL is from home.dk."""
        try:
            domain = extract_domain(url)
            return domain == "home.dk"
        except Exception:
            return False

    async def extract_image_url(self, html_content: str) -> Optional[str]:
        """
        Extracts the main property image URL, prioritizing meta tags and specific selectors.
        """
        if not html_content:
            return None

        logger.debug("Extracting image URL using HomeProvider logic.")
        try:
            soup = BeautifulSoup(html_content, 'lxml')

            # 1. Check meta tags (og:image) - Most reliable
            og_image = soup.find('meta', property='og:image')
            if og_image and og_image.get('content'):
                logger.debug("Found image URL in og:image meta tag.")
                return og_image['content']

            # 2. Look for specific image elements used by Home.dk
            # Combine selectors used in the Deno version
            specific_selectors = '.property-details-main__header img, .image-gallery-preview img'
            property_images = soup.select(specific_selectors)
            if property_images:
                for img in property_images:
                    src = img.get('src')
                    # Basic validation: check if src exists and looks like a URL
                    if src and src.startswith('http'):
                        logger.debug(f"Found image URL in specific selector: {specific_selectors}")
                        return src

            # 3. Fall back to generic image extraction from html_utils
            logger.debug("No specific image found, falling back to generic extraction.")
            generic_image_url = await html_utils.extract_first_image_url(html_content)
            if generic_image_url:
                return generic_image_url

            logger.debug("No suitable image URL found by HomeProvider.")
            return None

        except Exception as error:
            logger.error("Failed to extract image URL in HomeProvider", exc_info=error)
            return None

    async def parse_html(self, url: str, html_content: str) -> HtmlParseResult:
        """
        Parses Home.dk HTML, extracts text using generic utils, and image using specific logic.
        """
        logger.info(f"Parsing HTML with HomeProvider for URL: {url}")
        property_image_url: Optional[str] = None
        extracted_text: str = ""

        try:
            # Extract image using the overridden method
            property_image_url = await self.extract_image_url(html_content)

            # Extract text using generic utility
            extracted_text = await html_utils.extract_text_from_html(html_content)

            # For direct realtor links like Home.dk, the originalLink is the URL itself
            original_link = url

            return {
                "originalLink": original_link,
                "property_image_url": property_image_url,
                "extractedText": extracted_text,
            }

        except Exception as error:
            logger.error(f"Failed to parse HTML with HomeProvider for {url}", exc_info=error)
            # Return None values for data fields to match TS returning {}
            return {
                "originalLink": None,
                "property_image_url": None,
                "extractedText": None,
            }