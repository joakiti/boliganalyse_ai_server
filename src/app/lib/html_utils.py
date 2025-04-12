import logging
from typing import Optional
from bs4 import BeautifulSoup, Comment # Import BeautifulSoup
from .url_utils import resolve_url # Import resolve_url for relative paths

logger = logging.getLogger(__name__)

# Elements to ignore when extracting text
TEXT_IGNORE_TAGS = ['script', 'style', 'noscript', 'iframe', 'header'] # Keep nav and footer
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
        soup = BeautifulSoup(html_content, 'lxml') # Use lxml parser

        # Extract title and meta description first
        title_text = soup.title.string.strip() if soup.title else ""
        meta_desc_tag = soup.find('meta', attrs={'name': 'description'})
        meta_desc_text = meta_desc_tag['content'].strip() if meta_desc_tag and meta_desc_tag.get('content') else ""

        # Remove ignored tags and comments from the body or main content area
        body = soup.body if soup.body else soup # Fallback to whole soup if no body
        if body:
             for element in body(TEXT_IGNORE_TAGS):
                 element.decompose()
             for comment in body.find_all(string=lambda text: isinstance(text, Comment)):
                 comment.extract()
        else: # Should not happen with valid HTML, but as a safeguard
             for element in soup(TEXT_IGNORE_TAGS):
                 element.decompose()
             for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
                 comment.extract()
             body = soup # Use the cleaned soup

        # Get text from the cleaned body
        body_lines = [line.strip() for line in body.stripped_strings] if body else []
        body_text = ' '.join(body_lines) # Join with spaces

        # Combine title, meta description, and body text
        all_texts = [text for text in [title_text, meta_desc_text, body_text] if text]
        text = ' '.join(all_texts) # Join parts with spaces

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
        soup = BeautifulSoup(html_content, 'lxml')

        # 1. Check common meta tags (og:image, twitter:image)
        # Find potential og:image tags (case-insensitive property check)
        og_image_content = None
        meta_tags_property = soup.find_all('meta', attrs={'property': True})
        for tag in meta_tags_property:
            if tag['property'].lower() == 'og:image' and tag.get('content'):
                og_image_content = tag['content']
                logger.debug("Found image URL in og:image meta tag.")
                return resolve_url(base_url, og_image_content) # Return immediately

        # Find potential twitter:image tags (case-insensitive name check)
        twitter_image_content = None
        meta_tags_name = soup.find_all('meta', attrs={'name': True})
        for tag in meta_tags_name:
            # Common variations: 'twitter:image', 'twitter:image:src'
            if tag['name'].lower() in ('twitter:image', 'twitter:image:src') and tag.get('content'):
                twitter_image_content = tag['content']
                logger.debug("Found image URL in twitter:image meta tag.")
                return resolve_url(base_url, twitter_image_content) # Return immediately

        # 2. Look for image tags, prioritizing larger ones or those in specific containers
        # This requires more heuristics - simple approach for now: find first valid img src
        all_imgs = soup.find_all('img')
        for img in all_imgs:
            src = img.get('src')
            if src: # Check if src exists first
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
                    # Basic filtering for likely content images
                    logger.debug(f"Found potential image URL in img tag: {resolved_src}")
                    # Add width/height checks later if needed
                    return resolved_src

        logger.debug("No suitable image URL found in meta tags or img tags.")
        return None

    except Exception as error:
        logger.error("Failed to extract first image URL with BeautifulSoup", exc_info=error)
        return None

# Potential future addition: extract JSON-LD data
# async def extract_json_ld(html_content: str) -> List[Dict[str, Any]]:
#     ...