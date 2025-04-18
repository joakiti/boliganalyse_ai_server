import logging
import httpx
from typing import Optional, Union, List, Any, cast
from bs4 import BeautifulSoup, Comment, Tag, NavigableString, PageElement, ResultSet
from .url_utils import resolve_url

logger = logging.getLogger(__name__)

# Elements to ignore when extracting text
TEXT_IGNORE_TAGS: List[str] = ['script', 'style', 'noscript', 'iframe', 'header'] # Keep nav and footer
# Elements that often contain main content (can be used for targeted extraction if needed)
# CONTENT_TAGS = ['main', 'article', 'section', 'div[role="main"]']

async def extract_text_from_html(html_content: str) -> str:
    """
    Extracts readable text content from HTML using BeautifulSoup.
    Removes scripts, styles, comments, and other non-content elements.
    """
    if not html_content:
        return ""

    try:
        soup: BeautifulSoup = BeautifulSoup(html_content, 'lxml') # Use lxml parser

        # Extract title and meta description first
        title_text: str = ""
        if soup.title and isinstance(soup.title, Tag) and isinstance(soup.title.string, str):
            title_text = soup.title.string.strip()
            
        meta_desc_tag: Optional[Tag] = cast(Optional[Tag], soup.find('meta', attrs={'name': 'description'}))
        meta_desc_text: str = ""
        if meta_desc_tag and meta_desc_tag.get('content'):
            content = meta_desc_tag.get('content')
            if isinstance(content, str):
                meta_desc_text = content.strip()

        # Remove ignored tags and comments from the body or main content area
        body: Union[Tag, BeautifulSoup] = soup.body if soup.body else soup # Fallback to whole soup if no body
        if body:
             for element in body.find_all(TEXT_IGNORE_TAGS):
                 element.decompose()
             for comment in body.find_all(string=lambda text: isinstance(text, Comment)):
                 comment.extract()
        else: # Should not happen with valid HTML, but as a safeguard
             for element in soup.find_all(TEXT_IGNORE_TAGS):
                 element.decompose()
             for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
                 comment.extract()
             body = soup # Use the cleaned soup

        # Get text from the cleaned body
        body_lines: List[str] = [line.strip() for line in body.stripped_strings] if body else []
        body_text: str = ' '.join(body_lines) # Join with spaces

        # Combine title, meta description, and body text
        all_texts: List[str] = [text for text in [title_text, meta_desc_text, body_text] if text]
        text: str = ' '.join(all_texts) # Join parts with spaces

        # Get text, trying to preserve some structure with newlines
        # text = soup.get_text(separator='\n', strip=True)

        # Final whitespace cleanup (consolidate multiple spaces, remove leading/trailing)
        text = ' '.join(text.split())

        return text

    except Exception as error:
        logger.error("Failed to extract text from HTML with BeautifulSoup", exc_info=error)
        # Fallback to simpler regex-based extraction? Or just return empty.
        return "" # Return empty string on error

async def extract_first_image_url(html_content: str, base_url: str) -> Optional[str]:
    """
    Extract the first likely property image URL from HTML content using BeautifulSoup.
    Tries common meta tags first, then looks for large image elements.
    Resolves relative URLs using the provided base_url.
    """
    if not html_content:
        return None

    try:
        soup: BeautifulSoup = BeautifulSoup(html_content, 'lxml')

        # 1. Check common meta tags (og:image, twitter:image)
        # Find potential og:image tags (case-insensitive property check)
        meta_tags_property: ResultSet[PageElement] = soup.find_all('meta', attrs={'property': True})
        for tag in meta_tags_property:
            if not isinstance(tag, Tag):
                continue
            property_value = tag.get('property', '')
            if isinstance(property_value, str) and property_value.lower() == 'og:image':
                content = tag.get('content')
                if isinstance(content, str):
                    logger.debug("Found image URL in og:image meta tag.")
                    return resolve_url(base_url, content)

        # Find potential twitter:image tags (case-insensitive name check)
        meta_tags_name: ResultSet[PageElement] = soup.find_all('meta', attrs={'name': True})
        for tag in meta_tags_name:
            if not isinstance(tag, Tag):
                continue
            name_value = tag.get('name', '')
            if isinstance(name_value, str) and name_value.lower() in ('twitter:image', 'twitter:image:src'):
                content = tag.get('content')
                if isinstance(content, str):
                    logger.debug("Found image URL in twitter:image meta tag.")
                    return resolve_url(base_url, content)

        # 2. Look for image tags, prioritizing larger ones or those in specific containers
        all_imgs: ResultSet[PageElement] = soup.find_all('img')
        for img in all_imgs:
            if not isinstance(img, Tag):
                continue
            src = img.get('src')
            if isinstance(src, str):
                resolved_src = resolve_url(base_url, src)
                if resolved_src and resolved_src.startswith('http') and \
                   '.svg' not in resolved_src.lower() and \
                   'base64,' not in resolved_src.lower() and \
                   'logo' not in resolved_src.lower() and \
                   'icon' not in resolved_src.lower() and \
                   'avatar' not in resolved_src.lower() and \
                   'spinner' not in resolved_src.lower() and \
                   'loading' not in resolved_src.lower() and \
                   'placeholder' not in resolved_src.lower():
                    logger.debug(f"Found potential image URL in img tag: {resolved_src}")
                    return resolved_src

        logger.debug("No suitable image URL found in meta tags or img tags.")
        return None

    except Exception as error:
        logger.error("Failed to extract first image URL with BeautifulSoup", exc_info=error)
        return None

# HTML fetching utility
HTTP_TIMEOUT: float = 30.0  # seconds
USER_AGENT: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

async def fetch_html_content(url: str) -> str:
    """
    Fetch HTML content from a URL.
    """
    logger.info(f"Fetching HTML from {url}")
    headers: dict[str, str] = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml"
    }
    
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.text
            
    except Exception as e:
        logger.error(f"Error fetching URL {url}: {e}", exc_info=True)
        raise ValueError(f"Failed to fetch content from {url}")