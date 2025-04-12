import logging
from typing import Dict, Any, Optional

# Use try-except for optional import
try:
    from firecrawl import FirecrawlApp # Use the correct import name for the python lib
    from firecrawl.models import ScrapeResult # Import the response model
    firecrawl_available = True
except ImportError:
    firecrawl_available = False
    FirecrawlApp = None # Define as None if import fails
    ScrapeResult = None # Define as None if import fails

from src.app.core.config import settings
from .base_provider import BaseProvider, HtmlParseResult

# Use standard Python logging
logger = logging.getLogger(__name__) # Renamed logger instance

class FirecrawlProvider(BaseProvider):
    """Provider that uses Firecrawl for enhanced web scraping."""

    # Class level logger
    logger = logging.getLogger(__qualname__) # Use __qualname__ for class-specific logger name

    def __init__(self):
        self.firecrawl: Optional[FirecrawlApp] = None
        if not firecrawl_available:
            self.logger.warning("Firecrawl library not installed. FirecrawlProvider will be disabled.")
            return

        if settings.FIRECRAWL_API_KEY:
            try:
                self.firecrawl = FirecrawlApp(api_key=settings.FIRECRAWL_API_KEY)
                self.logger.info("Firecrawl client initialized.")
            except Exception as e:
                self.logger.error(f"Failed to initialize FirecrawlApp: {e}", exc_info=True)
                self.firecrawl = None # Ensure it's None if init fails
        else:
            self.logger.warning("Firecrawl API key not configured. FirecrawlProvider will be disabled.")

    @property
    def name(self) -> str:
        return "Firecrawl"

    def can_handle(self, url: str, html_content: Optional[str] = None) -> bool:
        """
        Check if this provider can handle the given URL.
        Enabled only if the library is installed and API key is configured.
        """
        # Check if library is installed and client was initialized successfully
        return self.firecrawl is not None

    async def parse_html(self, url: str, html_content: Optional[str] = None) -> HtmlParseResult:
        """
        Extract property data using Firecrawl service.
        Note: html_content is ignored as Firecrawl fetches fresh content.
        """
        if not self.firecrawl:
            self.logger.error("Firecrawl client not available or not initialized.")
            return {"error": "Firecrawl service not configured"}

        self.logger.info(f"Scraping URL with Firecrawl: {url}")
        extracted_text = ""
        image_url: Optional[str] = None

        try:
            # Use scrape method (async version if available, check library docs)
            # Assuming scrape is async or run in executor if it's sync
            # The python library's scrape method might be synchronous.
            # If so, it needs to be run in a thread pool executor in async context.
            # For simplicity here, assuming an async method exists or is handled.
            # Let's assume scrape is synchronous for now and needs executor:
            # import asyncio
            # loop = asyncio.get_running_loop()
            # response = await loop.run_in_executor(
            #     None, # Default executor
            #     lambda: self.firecrawl.scrape_url(url, params={'pageOptions': {'formats': ['markdown']}})
            # )
            # --- OR if the library has an async version ---
            response: Optional[ScrapeResult] = await self.firecrawl.ascrape_url(
                url,
                params={'pageOptions': {'formats': ['markdown']}} # Check correct params structure for python lib
            )


            if not response or not response.data:
                raise ValueError("No data received from Firecrawl scrape")

            # Access data correctly based on the Python library's ScrapeResult model
            scrape_data = response.data # Assuming data is the main attribute

            extracted_text = scrape_data.get('markdown', '') # Get markdown content
            metadata = scrape_data.get('metadata', {})

            # Extract image URL from metadata (similar logic to TS version)
            if metadata.get('ogImage'):
                image_url = metadata['ogImage']
            elif metadata.get('og:image'):
                image_url = metadata['og:image']
            elif isinstance(metadata.get('twitter'), dict) and metadata['twitter'].get('image'):
                 image_url = metadata['twitter']['image']
            elif isinstance(metadata.get('twitter:image'), str):
                 image_url = metadata['twitter:image']
            else:
                # Fallback: Look for first image in markdown
                import re
                img_match = re.search(r'!\[.*?\]\((https?://[^\)]+)\)', extracted_text)
                if img_match:
                    image_url = img_match.group(1)

            self.logger.info(f"Extracted image URL via Firecrawl: {image_url or 'No image found'}")

            return {
                "extractedText": extracted_text,
                "property_image_url": image_url,
                # Firecrawl doesn't provide an 'originalLink' directly
            }

        except Exception as e:
            self.logger.error(f"Error scraping URL {url} with Firecrawl: {e}", exc_info=True)
            # Match TS error structure: put error in extractedText, no 'error' key
            return {
                "extractedText": f"Failed to scrape content from {url} using Firecrawl: {e}",
                "property_image_url": None,
            }