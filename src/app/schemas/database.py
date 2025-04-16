from enum import Enum
from typing import Final


class DatabaseSchema(str, Enum):
    """Database schema names."""
    PRIVATE = "private"
    PUBLIC = "public"


class TableName(str, Enum):
    """Database table names."""
    APARTMENT_LISTINGS = "apartment_listings"


# Schema and table configuration
SCHEMA_CONFIG: Final[dict[str, str]] = {
    "schema": DatabaseSchema.PRIVATE,
    "apartment_listings": TableName.APARTMENT_LISTINGS,
} 