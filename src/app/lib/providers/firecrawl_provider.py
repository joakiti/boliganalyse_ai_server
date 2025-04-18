import logging
from typing import Dict, Any, Optional

from firecrawl import FirecrawlApp # Use the correct import name for the python lib
from src.app.core.config import settings
from .base_provider import BaseProvider
from src.app.schemas.parser import ParseResult # Import the new schema

# Use standard Python logging
logger = logging.getLogger(__name__) # Renamed logger instance

class FirecrawlProvider(BaseProvider):
    """Provider that uses Firecrawl for enhanced web scraping."""

    # Class level logger
    logger = logging.getLogger(__qualname__) # Use __qualname__ for class-specific logger name

    def __init__(self):
        self.firecrawl = FirecrawlApp(api_key=settings.FIRECRAWL_API_KEY)

    @property
    def name(self) -> str:
        return "Firecrawl"

    def can_handle(self, url: str, html_content: Optional[str] = None) -> bool:
        return self.firecrawl is not None

    async def parse_html(self, url: str, html_content: Optional[str] = None) -> ParseResult:
        if not self.firecrawl:
            self.logger.error("Firecrawl client not available or not initialized.")
            return ParseResult(
                original_link=None,
                extracted_text="Firecrawl service not configured"
            )

        self.logger.info(f"Scraping URL with Firecrawl: {url}")
        extracted_text = ""
        image_url: Optional[str] = None

        try:
            response: Optional[Any] = await self.firecrawl.scrape_url(
                url,
                params={'pageOptions': {'formats': ['markdown']}} # Check correct params structure for python lib
            )

            if not response or not response.data:
                raise ValueError("No data received from Firecrawl scrape")

            scrape_data = response.data

            extracted_text = scrape_data.get('markdown', '') # Get markdown content
            metadata = scrape_data.get('metadata', {})

            if metadata.get('ogImage'):
                image_url = metadata['ogImage']
            elif metadata.get('og:image'):
                image_url = metadata['og:image']
            elif isinstance(metadata.get('twitter'), dict) and metadata['twitter'].get('image'):
                 image_url = metadata['twitter']['image']
            elif isinstance(metadata.get('twitter:image'), str):
                 image_url = metadata['twitter:image']
            else:
                import re
                img_match = re.search(r'!\[.*?\]\((https?://[^\)]+)\)', extracted_text)
                if img_match:
                    image_url = img_match.group(1)

            self.logger.info(f"Extracted image URL via Firecrawl: {image_url or 'No image found'}")

            return ParseResult(
                original_link=None,  # Firecrawl doesn't provide redirect information
                extracted_text=extracted_text
            )

        except Exception as e:
            self.logger.error(f"Error scraping URL {url} with Firecrawl: {e}", exc_info=True)
            return ParseResult(
                original_link=None,
                extracted_text=f"Failed to scrape content from {url} using Firecrawl: {e}"
            )