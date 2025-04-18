import logging
from typing import Optional
from bs4 import BeautifulSoup
from pydantic import HttpUrl

from .base_provider import BaseProvider
from src.app.schemas.parser import ParseResult
from src.app.lib import html_utils
from src.app.lib.url_utils import extract_domain

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

    async def extract_image_url(self, html_content: str) -> Optional[HttpUrl]:
        """
        Extracts the main property image URL, prioritizing meta tags and specific Home.dk selectors.
        Falls back to generic image extraction if no specific images are found.
        """
        if not html_content:
            return None

        logger.debug("Extracting image URL using HomeProvider logic.")
        try:
            soup = BeautifulSoup(html_content, 'html.parser')

            # 1. Check meta tags (og:image) - Most reliable
            og_image = soup.find('meta', property='og:image')
            if og_image and og_image.get('content'):
                logger.debug("Found image URL in og:image meta tag.")
                try:
                    return HttpUrl(og_image['content'])
                except Exception:
                    logger.warning(f"og:image URL '{og_image['content']}' is not a valid HttpUrl.")

            # 2. Look for specific image elements used by Home.dk
            specific_selectors = '.property-details-main__header img, .image-gallery-preview img'
            property_images = soup.select(specific_selectors)
            if property_images:
                for img in property_images:
                    src = img.get('src')
                    if src and src.startswith('http'):
                        logger.debug(f"Found image URL in specific selector: {specific_selectors}")
                        try:
                            return HttpUrl(src)
                        except Exception:
                            logger.warning(f"Property image URL '{src}' is not a valid HttpUrl.")

            # 3. Fall back to generic image extraction
            logger.debug("No specific image found, falling back to generic extraction.")
            image_url = await html_utils.extract_first_image_url(soup)
            if image_url:
                try:
                    return HttpUrl(image_url)
                except Exception:
                    logger.warning(f"Generic image URL '{image_url}' is not a valid HttpUrl.")

            logger.debug("No suitable image URL found by HomeProvider.")
            return None

        except Exception as error:
            logger.error("Failed to extract image URL in HomeProvider", exc_info=error)
            return None

    async def parse_html(self, url: str, html_content: str) -> ParseResult:
        """
        Parses Home.dk HTML and extracts text using generic utils.
        """
        logger.info(f"Parsing HTML with HomeProvider for URL: {url}")
        try:
            extracted_text = await html_utils.extract_text_from_html(html_content)
            original_link = url
            validated_original_link: Optional[HttpUrl] = None

            if original_link:
                try:
                    validated_original_link = HttpUrl(original_link)
                except Exception:
                    logger.warning(f"Input URL '{original_link}' is not a valid HttpUrl for ParseResult.")

            return ParseResult(
                original_link=validated_original_link,
                extracted_text=extracted_text
            )

        except Exception as error:
            logger.error(f"Failed to parse HTML with HomeProvider for {url}", exc_info=error)
            return ParseResult(
                original_link=url,
                extracted_text=f"Failed to parse content from {url} using HomeProvider: {error}"
            )