import logging
import json
import httpx # Using httpx for consistency, though anthropic lib handles it
from typing import Dict, Any, Optional

# Use try-except for optional import
try:
    import anthropic
    anthropic_available = True
except ImportError:
    anthropic_available = False
    anthropic = None

from src.app.core.config import settings
from src.app.schemas.analyze import AnalysisResultData # For potential validation

logger = logging.getLogger(__name__)

# Constants from config (consider passing config/settings object instead)
CLAUDE_API_KEY = settings.ANTHROPIC_API_KEY
CLAUDE_ENDPOINT = "https://api.anthropic.com/v1/messages" # Default endpoint
CLAUDE_MODEL = "claude-3-5-sonnet-20240620" # Use the latest Sonnet model
CLAUDE_MAX_TOKENS = 4000
CLAUDE_TEMPERATURE = 0.5 # Lower temperature for more predictable JSON
CLAUDE_API_VERSION = "2023-06-01"
API_TIMEOUT = 180.0 # Longer timeout for potentially long AI calls

class AIAnalyzerService:
    """
    Service for performing AI analysis on text using the Anthropic Claude API.
    """
    def __init__(self):
        if not anthropic_available:
            raise ImportError("Anthropic library is not installed. Cannot use AIAnalyzerService.")
        if not CLAUDE_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY is not configured in settings.")

        # Initialize the async Anthropic client
        self.client = anthropic.AsyncAnthropic(api_key=CLAUDE_API_KEY, timeout=API_TIMEOUT)
        logger.info(f"Anthropic client initialized for model: {CLAUDE_MODEL}")

    def _create_analysis_prompt(self, text_content: str) -> str:
        """Creates the detailed prompt for Claude API."""
        # This prompt is adapted from the Deno version
        # Ensure the JSON structure example matches the Pydantic models in schemas/analyze.py
        return f"""
Du er ekspert i boliganalyser på det danske marked, og bruger idag din erfaring til at hjælpe fremtidige boligejere med at identificere skjulte risici og værdifulde fordele.

Din opgave er at lave en grundig analyse af en boligannonce baseret på den medfølgende tekst.

**VIGTIGT:** Dit svar SKAL være et JSON-objekt, der følger den specificerede struktur nedenfor. Inkluder IKKE nogen tekst før eller efter JSON-objektet. Start direkte med `{{` og slut direkte med `}}`.

**Analyseinstruktioner:**
1.  **Vurder boligen:** Analyser boligen ud fra den givne tekst. Brug din viden om det danske boligmarked til at udfylde eventuelle huller, men baser primært din analyse på den leverede tekst.
2.  **Identificer Risici:** Find mindst 5-8 relevante risici. Vær kreativ og tænk ud over det åbenlyse (f.eks. alder, materialer, beliggenhed, økonomi, juridiske aspekter). Angiv konkrete anbefalinger til køber. Brug "excerpt" til at citere den tekst, der understøtter din vurdering, eller angiv "Egen vurdering" hvis det er baseret på din ekspertise. Undlad at nævne manglende energimærke som en risiko, hvis det ikke er angivet i teksten.
3.  **Identificer Fordele:** Find mindst 5-8 relevante fordele. Fremhæv styrker, der giver værdi for køberen (f.eks. renoveringer, beliggenhedsmæssige fordele, unikke features).
4.  **Udfyld Egenskaber:** Udtæk specifikke data om boligen (adresse, pris, størrelse osv.) fra teksten. Hvis en oplysning mangler, udelad feltet eller sæt det til `null`. For energimærke, hvis det mangler, skriv "Se hos mægler".
5.  **Opsummering:** Skriv en kort opsummering af dine vigtigste konklusioner (2-4 sætninger).

**Målgruppe:**
Køberen er et par i 30'erne med et barn på 3 år og en samlet årsindkomst på 1.000.000 kr. Fokusér på aspekter, der er relevante for dem (f.eks. familievenlighed, økonomi, langsigtet værdi, vedligehold).

**JSON Output Format (Følg denne struktur NØJAGTIGT):**
```json
{{{{
  "summary": "Kort opsummering af de vigtigste konklusioner (2-4 sætninger).",
  "property": {{{{
    "address": "...",
    "price": "... kr.",
    "udbetaling": "... kr.",
    "pricePerM2": "... kr. per m²",
    "size": "... m²",
    "værelser": "...",
    "floor": "...",
    "boligType": "...",
    "ejerform": "...",
    "energiMaerke": "...",
    "byggeaar": "...",
    "renoveringsaar": "...",
    "maanedligeUdgift": "... kr."
  }}}},
  "risks": [
    {{{{
      "category": "Energi|Tilstand|Økonomi|Beliggenhed|Juridisk|Andet",
      "title": "Kort, præcis titel på risiko",
      "details": "Grundig vurdering af risikoen (2-3 sætninger)",
      "excerpt": "Relevant tekstcitat eller 'Egen vurdering'",
      "recommendations": [
        {{{{"promptTitle": "Spørg mægler/Undersøg nærmere", "prompt": "Relevant spørgsmål/handling"}}}}
      ]
    }}}}
  ],
  "highlights": [
    {{{{
      "icon": "home|building|map|key|piggy-bank|scale|star|heart|award|lightbulb|thumbs-up|check|flag|search",
      "title": "Kort præcis fordel",
      "details": "Begrundet forklaring af fordelen (2-3 sætninger)"
    }}}}
  ]
}}}}
```

**Boligannonce Tekst:**
```text
{text_content}
```

**Dit JSON svar:**
"""

    def _extract_json_from_response(self, raw_text: str) -> Dict[str, Any]:
        """Extracts the JSON object from Claude's response text."""
        try:
            # Find the start and end of the JSON object
            json_start = raw_text.find("{")
            json_end = raw_text.rfind("}")

            if json_start == -1 or json_end == -1:
                logger.error(f"Could not find JSON object in response: {raw_text}")
                raise ValueError("AI response did not contain a valid JSON object.")

            json_text = raw_text[json_start : json_end + 1]
            parsed_json = json.loads(json_text)
            return parsed_json
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from AI response: {e}\nResponse text: {raw_text}")
            raise ValueError(f"AI response was not valid JSON: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error extracting JSON: {e}", exc_info=True)
            raise

    async def analyze_text(self, text_content: str) -> Dict[str, Any]:
        """
        Analyzes the provided text content using the Claude API.

        Args:
            text_content: The combined text extracted from the listing page(s).

        Returns:
            A dictionary representing the structured analysis result.

        Raises:
            ValueError: If text_content is empty or API key is missing.
            RuntimeError: If the API call fails or returns an unexpected response.
        """
        logger.info(f"Starting AI analysis with text length: {len(text_content)}")
        if not text_content:
            raise ValueError("No text content provided for analysis.")
        if not self.client:
             raise RuntimeError("Anthropic client not initialized.")

        prompt = self._create_analysis_prompt(text_content)

        try:
            # Make the API call using the Anthropic async client
            message = await self.client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=CLAUDE_MAX_TOKENS,
                temperature=CLAUDE_TEMPERATURE,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            # Process the response
            if not message.content or not isinstance(message.content[0], anthropic.types.TextBlock):
                logger.error(f"Unexpected response structure from Claude: {message}")
                raise RuntimeError("Invalid response structure received from AI.")

            response_text = message.content[0].text
            logger.debug(f"Raw response text from Claude:\n{response_text}")

            # Extract JSON from the response
            analysis_json = self._extract_json_from_response(response_text)

            # Optional: Validate the extracted JSON against Pydantic schema
            try:
                _ = AnalysisResultData(**analysis_json) # Validate structure
                logger.info("AI analysis JSON successfully validated against schema.")
            except Exception as e: # Catch Pydantic ValidationError specifically if needed
                logger.warning(f"AI response JSON failed validation against AnalysisResultData schema: {e}")
                # Decide whether to raise an error or return the unvalidated JSON
                # For now, return it but log warning.
                pass

            return analysis_json

        except anthropic.APIConnectionError as e:
            logger.error(f"Anthropic API connection error: {e}", exc_info=True)
            raise RuntimeError("Failed to connect to AI service.") from e
        except anthropic.RateLimitError as e:
            logger.error(f"Anthropic API rate limit exceeded: {e}", exc_info=True)
            raise RuntimeError("AI service rate limit exceeded. Please try again later.") from e
        except anthropic.APIStatusError as e:
            logger.error(f"Anthropic API status error: {e.status_code} - {e.response}", exc_info=True)
            raise RuntimeError(f"AI service returned an error (Status {e.status_code}).") from e
        except Exception as e:
            logger.error(f"Unexpected error during AI analysis: {e}", exc_info=True)
            raise RuntimeError("An unexpected error occurred during AI analysis.") from e

    # Placeholder for tool calling method (can be added later)
    # async def analyze_with_tools(self, prompt: str) -> Dict[str, Any]:
    #     ...