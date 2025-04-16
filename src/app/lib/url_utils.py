import logging
from urllib.parse import urlparse, urlunparse, urljoin

logger = logging.getLogger(__name__)

from typing import Optional

def normalize_url(url: Optional[str]) -> Optional[str]:
    """
    Normalizes a URL by removing query parameters, fragments, and trailing slashes from the path.

    Args:
        url: The original URL string.

    Returns:
        The normalized URL string (scheme, netloc, path only),
        or None if the URL is invalid or cannot be parsed.
    """
    if not url:
        return None
    try:
        parsed = urlparse(url)

        if not parsed.scheme or not parsed.netloc:
            return None # Treat as invalid if scheme or netloc is missing

        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()
        path = parsed.path

        path = path.lower()

        return urlunparse((scheme, netloc, path, '', '', ''))

    except Exception as e:
        logger.warning(f"Error normalizing URL '{url}': {e}. Returning None.")
        return None

def extract_domain(url: Optional[str], remove_www: bool = True) -> Optional[str]:
    """
    Extracts the domain name (hostname) from a URL.

    Args:
        url: The URL string.
        remove_www: If True (default), removes 'www.' prefix from the domain.

    Returns:
        The extracted domain name (lowercase), or None if parsing fails or no domain exists.
    """
    if not url:
        return None
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname

        if not hostname: # Handle cases like 'http://' or invalid URLs
             logger.debug(f"No hostname found for URL '{url}'.")
             return None

        hostname = hostname.lower() # Normalize to lowercase

        return hostname
    except Exception as e:
        logger.warning(f"Error extracting domain from URL '{url}': {e}. Returning None.")
        return None

def is_absolute_url(url: str) -> bool:
    """
    Checks if a URL is absolute (has a scheme and netloc).

    Args:
        url: The URL string to check.

    Returns:
        True if the URL is absolute, False otherwise.
    """
    if not url:
        return False
    try:
        parsed = urlparse(url)
        return bool(parsed.scheme and parsed.netloc)
    except Exception:
        return False

def resolve_url(base_url: Optional[str], relative_url: Optional[str]) -> Optional[str]:
    """
    Resolves a relative URL against a base URL using urljoin.

    Args:
        base_url: The base URL string.
        relative_url: The relative URL string (or potentially absolute).

    Returns:
        The resolved absolute URL string, or the base_url if relative_url is None/empty,
        or the relative_url if base_url is None/empty, or None if both are None/empty
        or resolution fails.
    """
    # Handle None or empty inputs
    if not relative_url:
        return base_url # If relative is empty, the resolved URL is the base
    if not base_url:
        # If base is empty, return relative_url directly (matching test expectation)
        return relative_url

    # urljoin handles absolute relative_urls correctly
    try:
        # Let urljoin handle the path logic directly
        resolved = urljoin(base_url, relative_url)

        # Check if the result is a valid, absolute URL
        parsed_resolved = urlparse(resolved)
        if parsed_resolved.scheme and parsed_resolved.netloc:
            return resolved
        else:
            # Handle cases where urljoin might produce unexpected results with odd inputs
            # or if relative_url was not absolute and base_url was empty/None
            logger.warning(f"URL resolution resulted in a non-absolute or invalid URL: '{resolved}' from base '{base_url}' and relative '{relative_url}'. Returning None.")
            return None
    except Exception as e:
        logger.warning(f"Error resolving URL '{relative_url}' against base '{base_url}': {e}. Returning None.")
        return None