import pytest
from app.lib.html_utils import extract_text_from_html, extract_first_image_url

# --- Tests for extract_text_from_html ---

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "html_content, expected_text",
    [
        (
            "<html><head><title>Test</title><style>body { color: red; }</style></head><body><h1>Header</h1><p>Some text.</p><script>alert('hi');</script></body></html>",
            "Test Header Some text.",
        ),
        (
            "<body>Just body content <p>with a paragraph</p> and <span>span</span>.</body>",
            "Just body content with a paragraph and span.",
        ),
        (
            "<html><body><nav><a>Link</a></nav><main>Main content</main><footer>Footer</footer></body></html>",
            "Link Main content Footer", # Includes nav/footer by default
        ),
        (
            "<html><body>No relevant text</body></html>",
            "No relevant text",
        ),
        (
            "<html><head><meta name='description' content='Meta Desc'></head><body>Body</body></html>",
            "Meta Desc Body", # Includes meta description
        ),
        (
            "<html><body><p> Text with\nmultiple\nlines and   spaces. </p></body></html>",
            "Text with multiple lines and spaces.", # Whitespace normalization
        ),
        (
            "", # Empty string
            "",
        ),
        (
            None, # None input
            "",
        ),
        (
            "<html><body><!-- Comment --> Visible text</body></html>", # HTML comments
            "Visible text",
        ),
    ],
)
async def test_extract_text_from_html(html_content, expected_text):
    assert await extract_text_from_html(html_content) == expected_text

# --- Tests for extract_first_image_url ---

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "html_content, base_url, expected_image_url",
    [
        # Basic image tag
        (
            "<html><body><img src='image.jpg'></body></html>",
            "http://example.com",
            "http://example.com/image.jpg",
        ),
        # og:image meta tag (preferred)
        (
            "<html><head><meta property='og:image' content='http://example.com/og_image.png'></head><body><img src='other.jpg'></body></html>",
            "http://example.com",
            "http://example.com/og_image.png",
        ),
        # og:image with relative URL
        (
            "<html><head><meta property='og:image' content='/img/og_relative.gif'></head><body></body></html>",
            "http://example.com/path/",
            "http://example.com/img/og_relative.gif",
        ),
        # Multiple images, first relevant one chosen
        (
            "<html><body><img src='logo.svg'><img src='main.png'><img src='icon.ico'></body></html>",
            "http://example.com",
            "http://example.com/main.png", # Skips svg, takes png
        ),
        # Image inside link
        (
            "<html><body><a><img src='linked_image.jpeg'></a></body></html>",
            "http://example.com",
            "http://example.com/linked_image.jpeg",
        ),
        # Image with data URI (should be ignored)
        (
            "<html><body><img src='data:image/gif;base64,R0lGODlhAQABAIAAAAUEBAAAACwAAAAAAQABAAACAkQBADs='><img src='real.webp'></body></html>",
            "http://example.com",
            "http://example.com/real.webp",
        ),
        # No relevant images
        (
            "<html><body><img src='logo.svg'><img src='favicon.ico'></body></html>",
            "http://example.com",
            None,
        ),
        # Empty src
        (
            "<html><body><img src=''></body></html>",
            "http://example.com",
            None,
        ),
        # No images at all
        (
            "<html><body>Just text</body></html>",
            "http://example.com",
            None,
        ),
        # Invalid HTML
        (
            "<html><body><img src='valid.jpg' </body</html>", # Malformed tag
            "http://example.com",
            "http://example.com/valid.jpg", # BeautifulSoup might still parse it
        ),
        # og:image takes precedence over img, even if img comes first
        (
             "<html><head><meta property='og:image' content='og.jpg'></head><body><img src='first.png'></body></html>",
             "http://example.com",
             "http://example.com/og.jpg",
        ),
         # Case sensitivity check for og:image property
        (
             "<html><head><meta property='OG:IMAGE' content='og_caps.jpg'></head><body></body></html>",
             "http://example.com",
             "http://example.com/og_caps.jpg",
        ),
        # Base URL variations
        (
            "<html><body><img src='relative.png'></body></html>",
            "http://example.com/deep/path/",
            "http://example.com/deep/path/relative.png",
        ),
        (
            "<html><body><img src='/abs_path.jpg'></body></html>",
            "http://example.com/deep/path/",
            "http://example.com/abs_path.jpg",
        ),
        # Empty HTML
        (
            "",
            "http://example.com",
            None,
        ),
        # None HTML
        (
            None,
            "http://example.com",
            None,
        ),
    ],
)
async def test_extract_first_image_url(html_content, base_url, expected_image_url):
    assert await extract_first_image_url(html_content, base_url) == expected_image_url