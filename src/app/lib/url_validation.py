import logging
from typing import Dict, Any, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# List of supported real estate domains
SUPPORTED_DOMAINS = [
    # Major aggregators
    'boligsiden.dk',
    
    # Major real estate chains
    'home.dk',
    'nybolig.dk',
    'edc.dk',
    'danbolig.dk',
    'estate.dk',
    'realmaeglerne.dk',
    
    # Rental properties
    'lejebolig.dk',
    'boligportal.dk',
    
    # Other real estate agencies
    'lokalbolig.dk',
    'boligone.dk',
    '1848.dk',
    'dinmaegler.dk',
    'lilholts.dk',
    'coldwellbanker.dk'
]

def extract_domain(url: str) -> str:
    """
    Extract the domain from a URL.
    
    Args:
        url: The URL to extract the domain from
        
    Returns:
        The domain as a string
    """
    parsed_url = urlparse(url)
    domain = parsed_url.netloc.lower()
    
    # Remove www. prefix if present
    if domain.startswith('www.'):
        domain = domain[4:]
        
    return domain

def validate_listing_url(url: str) -> Dict[str, Any]:
    """
    Validates that a URL is from a supported real estate provider.
    
    Args:
        url: URL to validate
        
    Returns:
        Dictionary with validation result and error message if invalid
    """
    # Check if URL is provided
    if not url:
        return {"valid": False, "error": "Link er ikke angivet"}
    
    try:
        # Parse URL to check structure
        parsed_url = urlparse(url)
        domain = extract_domain(url)
        
        # Check for ViewPage in the URL path
        if 'viewpage' in parsed_url.path.lower():
            return {
                "valid": False,
                "error": "Linket ser ud til at være en bolig der ikke er til salg."
            }
        
        # Special case: For Boligsiden URLs, use the more strict validation
        if domain == 'boligsiden.dk':
            return validate_boligsiden_url(url)
        
        # For all other domains, just check if the domain is supported
        if domain not in SUPPORTED_DOMAINS:
            return {
                "valid": False,
                "error": "Linket skal være fra en understøttet boligportal. Se listen over understøttede portaler på forsiden."
            }
        
        return {"valid": True}
    except Exception as e:
        logger.error(f"Error validating URL {url}: {e}")
        return {
            "valid": False,
            "error": "Linket er ugyldigt"
        }

def validate_boligsiden_url(url: str) -> Dict[str, Any]:
    """
    Legacy function to validate Boligsiden URLs for backward compatibility.
    
    Args:
        url: URL to validate
        
    Returns:
        Dictionary with validation result and error message if invalid
    """
    # Check if URL is provided
    if not url:
        return {"valid": False, "error": "Link er ikke angivet"}
    
    try:
        # Parse URL to check structure
        parsed_url = urlparse(url)
        domain = extract_domain(url)
        
        # Check hostname (allow both www and non-www versions)
        if domain != 'boligsiden.dk':
            return {
                "valid": False,
                "error": "Linket skal være fra boligsiden.dk"
            }
        
        # Check for udbud parameter
        query_params = dict(param.split('=') for param in parsed_url.query.split('&') if '=' in param)
        if 'udbud' not in query_params:
            return {
                "valid": False,
                "error": "Linket skal indeholde en udbuds-ID (udbud=...)"
            }
        
        if 'viewpage' in parsed_url.path.lower():
            return {
                "valid": False,
                "error": "Linket ser ud til at være en bolig der ikke er til salg."
            }
        
        return {"valid": True}
    except Exception as e:
        logger.error(f"Error validating Boligsiden URL {url}: {e}")
        return {
            "valid": False,
            "error": "Linket er ugyldigt"
        } 