from pydantic import BaseModel, HttpUrl
from typing import Optional

class ParseResult(BaseModel):

    original_link: Optional[HttpUrl] = None
    extracted_text: Optional[str] = None
