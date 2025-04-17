import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Awaitable

from src.app.schemas.parser import ParseResult # Import the new schema

# Assuming html_utils will be created later
# from app.lib import html_utils

logger = logging.getLogger(__name__)


class BaseProvider(ABC):
    """Abstract base class for all real estate listing providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Get the name of this provider (e.g., 'Boligsiden.dk')."""
        pass

    @abstractmethod
    def can_handle(self, url: str, html_content: Optional[str] = None) -> bool:
        """
        Check if this provider can handle the given URL and optionally HTML content.

        Args:
            url: The URL of the listing.
            html_content: Optional HTML content (useful for providers like JSON-LD
                          that inspect content).

        Returns:
            True if the provider can handle the URL/content, False otherwise.
        """
        pass

    @abstractmethod
    async def parse_html(self, url: str, html_content: str) -> ParseResult:
        """
        Parse HTML content to extract structured data.

        Args:
            url: The URL from which the HTML was fetched.
            html_content: The HTML content string to parse.

        Returns:
            A ParseResult object containing extracted data, primarily:
             - original_link: URL of the original listing if redirected.
             - extracted_text: Main textual content extracted from the page.
        """
        pass

    async def extract_image_url(self, html_content: str) -> Optional[str]:
        """
        Default implementation to extract the first likely image URL.
        Providers should override this if they have a more specific method.
        Relies on html_utils module (to be created).
        """
        try:
            # Placeholder for actual implementation using html_utils
            # image_url = await html_utils.extract_first_image_url(html_content)
            logger.debug("Using base extract_image_url (placeholder).")
            # Simulate finding an image for now
            if "<img" in html_content:
                 # A very basic placeholder check
                 return "placeholder_image_url_from_base.jpg"
            return None
        except Exception as error:
            logger.error("Failed to extract image URL in BaseProvider", exc_info=error)
            return None