import pytest
from app.lib.url_utils import (
    normalize_url,
    extract_domain,
    is_absolute_url,
    resolve_url,
)

# --- Tests for normalize_url ---

@pytest.mark.parametrize(
    "input_url, expected_output",
    [
        ("http://example.com", "http://example.com"),
        ("https://example.com/", "https://example.com"),
        ("http://www.example.com", "http://www.example.com"),
        ("https://WWW.EXAMPLE.COM/Path?Query=1#Frag", "https://www.example.com/path"),
        ("http://example.com/path/", "http://example.com/path"),
        ("http://example.com/path?a=1&b=2", "http://example.com/path"),
        ("http://example.com/path#section", "http://example.com/path"),
        ("http://example.com:8080/path", "http://example.com:8080/path"), # Keep port
        ("ftp://example.com/file", "ftp://example.com/file"), # Other schemes
        ("", None),
        (None, None),
        ("invalid-url", None),
        ("http://", None), # Invalid domain part
    ],
)
def test_normalize_url(input_url, expected_output):
    assert normalize_url(input_url) == expected_output

# --- Tests for extract_domain ---

@pytest.mark.parametrize(
    "input_url, expected_output",
    [
        ("http://example.com", "example.com"),
        ("https://www.example.com/path?query=1", "www.example.com"),
        ("http://sub.example.co.uk/page", "sub.example.co.uk"),
        ("https://example.com:443/", "example.com"),
        ("http://192.168.1.1/page", "192.168.1.1"),
        ("ftp://user:pass@example.com:21/dir", "example.com"),
        ("example.com", None), # Needs scheme
        ("invalid-url", None),
        ("", None),
        (None, None),
        ("http://", None),
    ],
)
def test_extract_domain(input_url, expected_output):
    assert extract_domain(input_url) == expected_output

# --- Tests for is_absolute_url ---

@pytest.mark.parametrize(
    "input_url, expected_output",
    [
        ("http://example.com", True),
        ("https://example.com/path", True),
        ("ftp://example.com", True),
        ("//example.com/path", False), # Scheme-relative is not considered absolute by this func
        ("/path/to/page", False),
        ("page.html", False),
        ("sub/page.html", False),
        ("", False),
        (None, False),
        ("invalid-url", False), # Doesn't check validity, just presence of scheme
    ],
)
def test_is_absolute_url(input_url, expected_output):
    assert is_absolute_url(input_url) == expected_output

# --- Tests for resolve_url ---

@pytest.mark.parametrize(
    "base_url, relative_url, expected_output",
    [
        ("http://example.com/path/", "page.html", "http://example.com/path/page.html"),
        ("http://example.com/path/file.html", "other.html", "http://example.com/path/other.html"),
        ("http://example.com/path/", "/abs/path", "http://example.com/abs/path"),
        ("http://example.com/path/", "//other.com/res", "http://other.com/res"), # Scheme relative
        ("https://example.com/path/", "//other.com/res", "https://other.com/res"), # Scheme relative https
        ("http://example.com/path/", "http://absolute.com/page", "http://absolute.com/page"), # Already absolute
        ("http://example.com/a/b/c", "../d", "http://example.com/a/d"),
        ("http://example.com/a/b/c", "../../d", "http://example.com/d"),
        ("http://example.com/a/b/c", "/d", "http://example.com/d"),
        ("http://example.com", "page.html", "http://example.com/page.html"),
        ("http://example.com/", "page.html", "http://example.com/page.html"),
        ("http://example.com/path", "page.html", "http://example.com/page.html"), # Base is treated as dir if no trailing / ? urljoin behavior
        ("http://example.com/path/", "", "http://example.com/path/"), # Empty relative
        ("", "page.html", "page.html"), # Empty base
        ("http://example.com", None, "http://example.com"), # None relative
        (None, "page.html", "page.html"), # None base
        ("http://example.com/path?query=1#frag", "page.html", "http://example.com/page.html"), # Base with query/frag
    ],
)
def test_resolve_url(base_url, relative_url, expected_output):
    assert resolve_url(base_url, relative_url) == expected_output