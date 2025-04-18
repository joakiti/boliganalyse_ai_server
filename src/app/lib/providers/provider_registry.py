import logging
from typing import Optional, List

# Import all implemented provider classes
from .base_provider import BaseProvider
from .boligsiden_provider import BoligsidenProvider
from .home_provider import HomeProvider
from .danbolig_provider import DanboligProvider
from .edc_provider import EdcProvider
from .firecrawl_provider import FirecrawlProvider
from .json_ld_provider import JsonLdProvider


logger = logging.getLogger(__name__)

class ProviderRegistry:
    """
    Singleton registry for managing and selecting real estate listing providers.
    """
    _instance: Optional['ProviderRegistry'] = None
    providers: List[BaseProvider] = []

    def __new__(cls):
        if cls._instance is None:
            logger.info("Creating ProviderRegistry instance.")
            cls._instance = super(ProviderRegistry, cls).__new__(cls)
            cls._instance._initialize_providers()
        return cls._instance

    def _initialize_providers(self):
        """Registers all available providers in a specific order of priority."""
        self.providers = [] # Ensure list is empty before initializing

        logger.info("Initializing and registering providers...")

        # Register providers - Order matters! More specific providers first.
        # 1. Major specific providers
        self.register_provider(BoligsidenProvider())
        self.register_provider(HomeProvider())
        self.register_provider(DanboligProvider()) # Uses Firecrawl but has specific cleanup
        self.register_provider(EdcProvider())      # Uses JSON-LD but specific domain check

        # 2. Generic mechanism providers
        # JsonLdProvider checks content, so it should come before Firecrawl if possible
        self.register_provider(JsonLdProvider())

        # Firecrawl as a general scraper (if configured)
        self.register_provider(FirecrawlProvider())

        # 3. Fallback (if needed - currently commented out in Deno version)
        # self.register_provider(FallbackProvider())

        logger.info(f"Registered {len(self.providers)} providers.")

    def register_provider(self, provider: BaseProvider):
        """Adds a provider instance to the registry."""
        # Check if provider initialization failed (e.g., Firecrawl API key missing)
        # This check might need refinement based on how providers signal failure.
        # For Firecrawl, we check if self.firecrawl is None in its can_handle.
        # For others, assume they are always available unless they raise errors.
        self.providers.append(provider)
        logger.debug(f"Registered provider: {provider.name}")

    def get_provider_for_content(self, url: str, html_content: Optional[str] = None) -> BaseProvider:
        """
        Finds the first registered provider that can handle the given URL and HTML content.

        Args:
            url: The URL of the listing.
            html_content: Optional HTML content of the page. Only required for
                          providers that need to inspect content (like JSON-LD).

        Returns:
            The first matching BaseProvider instance.

        Raises:
            ValueError: If no suitable provider is found.
            :rtype: object
        """
        logger.debug(f"Attempting to find provider for URL: {url}")
        for provider in self.providers:
            try:
                if provider.can_handle(url, html_content):
                    logger.info(f"Using provider '{provider.name}' for URL: {url}")
                    return provider
            except Exception as e:
                 logger.error(f"Error checking provider {provider.name} for URL {url}", exc_info=e)
                 # Continue to the next provider

        logger.error(f"No suitable provider found for URL: {url}")
        raise ValueError(f"Unsupported URL or content: No provider could handle {url}")

# Function to easily get the singleton instance
def get_provider_registry() -> ProviderRegistry:
    return ProviderRegistry()