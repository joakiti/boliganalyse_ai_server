import logging
from typing import Optional

from .json_ld_provider import JsonLdProvider # Import the parent provider
from src.app.lib.url_utils import extract_domain # Import url utils

logger = logging.getLogger(__name__)

class EdcProvider(JsonLdProvider):
    """Provider implementation for EDC.dk, primarily using JSON-LD."""

    @property
    def name(self) -> str:
        return "EDC" # Use a more user-friendly name

    def can_handle(self, url: str, html_content: Optional[str] = None) -> bool:
        """
        Checks if the URL is from edc.dk AND if the content has JSON-LD
        (checked by the parent class's can_handle method).
        """
        try:
            domain = extract_domain(url)
            if domain == "edc.dk":
                # If domain matches, delegate to parent (JsonLdProvider)
                # to check if JSON-LD is actually present in the content.
                # This ensures we only handle EDC pages that provide JSON-LD.
                has_json_ld = super().can_handle(url, html_content)
                if not has_json_ld:
                     logger.debug(f"URL is edc.dk but no JSON-LD found: {url}")
                return has_json_ld
            return False
        except Exception:
            return False

    # No need to override parse_html or extract_image_url unless EDC
    # requires specific handling different from the generic JsonLdProvider.
    # For now, we assume the parent implementation is sufficient.