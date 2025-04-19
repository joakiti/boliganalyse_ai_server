import logging
import re
import httpx
from typing import Optional
from urllib.parse import urlparse, parse_qs
from pydantic import HttpUrl
from .base_provider import BaseProvider
from src.app.schemas.parser import ParseResult
from src.app.lib import html_utils
from src.app.lib.url_utils import extract_domain

logger = logging.getLogger(__name__)

# Constants from analysis_service - consider moving to a shared place or config
HTTP_TIMEOUT = 30.0 # seconds
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

class BoligsidenProvider(BaseProvider):
    """Provider implementation for Boligsiden.dk."""

    @property
    def name(self) -> str:
        return "Boligsiden.dk"

    def can_handle(self, url: str, html_content: Optional[str] = None) -> bool:
        """Checks if the URL is from boligsiden.dk."""
        try:
            # Use extract_domain utility function
            domain = extract_domain(url)
            return domain == "www.boligsiden.dk"
        except Exception:
            return False

    async def _extract_source_url(self, url: str) -> Optional[str]:
        """
        Extracts the original source URL by following Boligsiden's redirect.
        """
        try:
            parsed_url = urlparse(url)
            query_params = parse_qs(parsed_url.query)
            udbud_list = query_params.get('udbud')

            if not udbud_list or not udbud_list[0]:
                logger.info(f"No 'udbud' parameter found in Boligsiden URL: {url}")
                return None

            case_id = udbud_list[0]
            redirect_url = f"https://www.boligsiden.dk/viderestilling/{case_id}"
            logger.warning(f"Following Boligsiden redirect URL: {redirect_url}")

            headers = {"User-Agent": USER_AGENT}
            async with httpx.AsyncClient(follow_redirects=True, timeout=HTTP_TIMEOUT) as client:
                # Use HEAD request to get final URL without downloading body
                response = await client.head(redirect_url, headers=headers)
                response.raise_for_status() # Check for errors

                final_url = str(response.url) # The URL after following redirects
                logger.info(f"Resolved Boligsiden redirect to final URL: {final_url}")

                # Avoid returning the redirector URL itself if redirect failed somehow
                if "boligsiden.dk/viderestilling" in final_url:
                     logger.warning(f"Redirect did not resolve away from viderestilling for {url}")
                     return None

                return final_url
        except Exception as error:
            logger.error(f"Failed to extract source URL from {url}", exc_info=error)
            return None

    async def parse_html(self, url: str, html_content: str) -> ParseResult:

        try:
            extracted_text = await html_utils.extract_text_from_html(html_content)

            original_link = await self._extract_source_url(url)

            # Clean specific phrases from extracted text
            phrases_to_remove = [
                re.compile(r"Se hvilke internetforbindelser, der er tilgængelige på adressen\. Bemærk, at mobildækning ikke er oplyst\.", re.IGNORECASE),
                re.compile(r"RadonrisikoRadonrisikoen vurderes til at være ukendtUkendt", re.IGNORECASE),
            ]
            cleaned_text = extracted_text
            for phrase_re in phrases_to_remove:
                cleaned_text = phrase_re.sub("", cleaned_text).strip()

            # Consolidate whitespace again after removals
            cleaned_text = ' '.join(cleaned_text.split())

            validated_original_link: Optional[HttpUrl] = None

            if original_link:
                try:
                    validated_original_link = HttpUrl(original_link)
                except Exception:
                    logger.warning(f"Extracted original link '{original_link}' is not a valid HttpUrl.")

            return ParseResult(
                original_link=validated_original_link,
                extracted_text=cleaned_text
            )

        except Exception as error:
            logger.error(f"Failed to parse HTML with BoligsidenProvider for {url}", exc_info=error)
            # Return ParseResult with error message in extracted_text
            return ParseResult(
                 extracted_text=f"Failed to parse content from {url} using BoligsidenProvider: {error}"
            )