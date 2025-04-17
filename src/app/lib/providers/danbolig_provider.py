import logging
from typing import Optional

from .firecrawl_provider import FirecrawlProvider # Inherit from Firecrawl
from src.app.lib.url_utils import extract_domain # Import url utils
from src.app.schemas.parser import ParseResult # Import the new schema

logger = logging.getLogger(__name__)

class DanboligProvider(FirecrawlProvider):
    """Provider implementation for Danbolig.dk, using Firecrawl with specific cleanup."""

    # Override the logger to use the specific class name
    logger = logging.getLogger(__qualname__)

    @property
    def name(self) -> str:
        return "Danbolig"

    def can_handle(self, url: str, html_content: Optional[str] = None) -> bool:
        """Checks if the URL is from danbolig.dk."""
        # Also check if the parent (FirecrawlProvider) can handle it (i.e., is configured)
        firecrawl_can_handle = super().can_handle(url, html_content)
        if not firecrawl_can_handle:
            return False # Don't handle if Firecrawl isn't available

        try:
            domain = extract_domain(url)
            return domain == "danbolig.dk"
        except Exception:
            return False

    async def parse_html(self, url: str, html_content: Optional[str] = None) -> ParseResult:
        """
        Uses Firecrawl to get markdown, then cleans it specifically for Danbolig.
        """
        firecrawl_result: ParseResult = await super().parse_html(url)

        if not firecrawl_result.extracted_text or "Failed to scrape content" in firecrawl_result.extracted_text:
            self.logger.warning(f"Firecrawl failed or returned error for {url}. Returning result as is.")
            return firecrawl_result

        extracted_text = firecrawl_result.extracted_text

        cleaned_markdown = extracted_text # Default to original if cleaning fails
        if extracted_text:
            self.logger.debug("Cleaning Danbolig-specific markdown from Firecrawl output.")
            try:
                cleaned_markdown = self._clean_markdown(extracted_text)
            except Exception as clean_err:
                 self.logger.error(f"Error cleaning Danbolig markdown for {url}: {clean_err}", exc_info=True)
                 # Keep the original extracted_text if cleaning fails
                 cleaned_markdown = extracted_text
        else:
            self.logger.warning(f"No extracted text from Firecrawl to process for {url}")
            cleaned_markdown = "" # Ensure it's an empty string if None initially

        # Return a new ParseResult with the cleaned text and original link from Firecrawl
        return ParseResult(
            extracted_text=cleaned_markdown,
            original_link=firecrawl_result.original_link # Preserve original_link if found by Firecrawl (likely None)
        )

    def _clean_markdown(self, markdown: str) -> str:
        """
        Removes common boilerplate/cookie consent text from Danbolig's Firecrawl output.
        """
        # Markers identified from the Deno version
        start_marker = "Kun nødvendige formålOK til valgteTilpas"
        end_marker = "## Kontakt os" # Assuming this is a reliable end marker

        # Find the last occurrence of the start marker, as it might appear multiple times
        start_index = markdown.rfind(start_marker)
        # If found, start cleaning after the marker
        effective_start_index = start_index + len(start_marker) if start_index != -1 else 0

        # Find the last occurrence of the end marker
        end_index = markdown.rfind(end_marker)
        # If found, end cleaning before the marker; otherwise, use the end of the string
        effective_end_index = end_index if end_index != -1 else len(markdown)

        # Ensure start index is not after end index
        if effective_start_index >= effective_end_index:
             self.logger.warning("Danbolig markdown cleaning markers found in unexpected order or overlapping. Returning original markdown.")
             return markdown # Avoid returning empty string if markers are weird

        cleaned = markdown[effective_start_index:effective_end_index].strip()
        self.logger.debug(f"Cleaned markdown length: {len(cleaned)}")
        return cleaned