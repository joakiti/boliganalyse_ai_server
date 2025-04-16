import logging
import json
import asyncio
from typing import Dict, Any, Optional, List, Union

import anthropic
from anthropic.types import (
    Message,
    ContentBlock,
    TextBlockParam,
    Usage,
    MessageParam,
    MessageCreateParams,
    ContentBlockDeltaEvent,
    ContentBlockStartEvent,
    ContentBlockStopEvent,
    MessageDeltaEvent,
    MessageStartEvent,
    MessageStopEvent,
    MessageStreamEvent,
)
from src.app.core.config import settings
from src.app.schemas.analyze import AnalysisResultData # For potential validation
from src.app.schemas.tool_calling import ToolCallRequest, ToolCallResponse # Assuming these are still relevant for internal logic
from src.app.services.tool_registry import ToolRegistryService
from src.app.services.tools.dst_api_tools import (
    GetSubjectsTool,
    GetTablesTool,
    GetTableInfoTool,
    GetDataTool,
)

logger = logging.getLogger(__name__)

# Constants from config
CLAUDE_API_KEY = settings.ANTHROPIC_API_KEY
CLAUDE_MODEL = "claude-3-5-sonnet-20240620"
CLAUDE_MAX_TOKENS = 4096 # Increased slightly as per Claude docs recommendation for tool use
CLAUDE_TEMPERATURE = 0.5
API_TIMEOUT = 180.0
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5

# Headers (Anthropic library usually handles versioning, Beta might be needed)
# ANTHROPIC_VERSION_HEADER = "2023-06-01"
# ANTHROPIC_BETA_HEADER = "tools-2024-04-04" # Check if still needed

class AIAnalyzerService:
    """
    Service for performing AI analysis on text using the Anthropic Claude API
    with tool calling capabilities.
    """
    def __init__(self):
        if not CLAUDE_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY is not set in environment variables.")
        
        self.client = anthropic.Client(api_key=CLAUDE_API_KEY)
        self.tool_registry = ToolRegistryService()

        # Instantiate and register DST tools
        self.tool_registry.register_tool(GetSubjectsTool())
        self.tool_registry.register_tool(GetTablesTool())
        self.tool_registry.register_tool(GetTableInfoTool())
        self.tool_registry.register_tool(GetDataTool())
        # Do NOT register Dingeo tool here as per instructions
        logger.info(f"Registered tools: {[definition.name for definition in self.tool_registry.get_all_tool_definitions()]}")


    def _create_analysis_prompt(self, text_content: str) -> str:
        """Creates the detailed prompt for Claude API, adapted from TypeScript version."""
        # Ensure the JSON structure example matches the Pydantic models in schemas/analyze.py
        # Note: Removed explicit JSON block ```json ... ``` around the example structure
        # as Claude generally prefers the structure directly described.
        # Note: Removed the explicit {{{{ and }}}} as they might confuse the f-string formatting or Claude.
        # Using standard { and } for the JSON example.
        return f"""
Du er ekspert i boliganalyser på det danske marked, og bruger idag din erfaring til at hjælpe fremtidige boligejere med at identificere skjulte risici og værdifulde fordele.

Din opgave er at lave en grundig analyse af en boligannonce

Forsøg at vær kreativ med dine fordele og risici, og tænk ud over det åbenlyse - hvad kan være skjulte fordele og risici - og hvad kan være en potentiel dealbreaker for køberen?

Vær opmærksom på, at du skal vurdere boligen ud fra den givne tekst, men du må godt bruge din egen viden og erfaring til at udfylde huller, hvis du ved et område/materiale/boligtype eller noget fjerde,
    er kendt for noget specifikt.

Sørg ALTID for at have en reference, til hvad du har brugt til at komme frem til dit svar, og inkluder det i feltet "excerpt" i JSON-formatet.

Udover at identificere risici og fordele, skal du også give afgive en kort rapport om boligen, og de kommunale forhold, som kan have indflydelse på boligens værdi.

Det er vigtigt, at du fokusere på ting, der er vigtige for køberen.

Køberen er et par i 30'erne, med et barn på 3 år. De er begge i arbejde, og har en samlet indkomst på 1.000.000 kr. om året.
Køberen er interesseret i at vide, om boligen er et godt køb, og om der er noget, der kan påvirke boligens værdi.
Køberen er også interesseret i at vide, om boligen er et godt sted at bo, og om der er noget, der kan påvirke boligens værdi.


**OPGAVE 1**

Du skal forsøge at perskektivere boligen i forhold til Danmarks Statistik og Dingeo.dk data, og lave en grundig analyse af boligen udfra disse data.

Vælg et par fokusområder, som du vil undersøge nærmere med Danmarks Statistik og Dingeo.dk, som er relevante for din købers profil og boligopslaget.

Du har adgang til Danmarks Statistik og Dingeo.dk via tool_calls:

1. FOR DANMARKS STATISTIK:
- Først, brug get_dst_subjects uden parametre for at få de gyldige top-level subject codes
- Brug derefter get_dst_tables med subject code for at få de gyldige table codes
- Brug derefter get_dst_table_info med table code for at få de gyldige variable
- Brug til sidst get_dst_data med table code og de variable, du vil have data for

2. FOR DINGEO.DK:
- Brug get_address_data med adressen fra boligopslaget for at få detaljerede ejendomsdata
- Dette værktøj giver dig data om ejendommens værdi, størrelse, energimærke, byggematerialer, og andre vigtige detaljer
- Brug disse data til at give en mere præcis vurdering af boligens stand og værdi

Vær OBS på at bruge de rigtige parametre til funktionerne.


**OPGAVE 2**
1. Analyser boligannoncens detaljer, sammen med dine kommunale observationer. Du kan overveje at inkludere disse områder:

**BASAL INFORMATION:**
- Generelle oplysninger: adresse, pris, boligtype, ejerform, størrelse, antal værelser, etage
- Bygningsdetaljer: byggeår, renoveringsår, energimærke, tag, vægge, konstruktionsmateriale
- Økonomi: udbetaling, månedlig ydelse, ejerudgift, boligafgift, grundskyld, fællesudgifter
- Tilstand: generel stand, vedligeholdelsesniveau, energimærke, rapporter (hvis nævnt)
- Området: kvarter, transport, institutioner, indkøbsmuligheder, rekreative områder
- Historik: prisændringer, tid på markedet, tidligere salg
- Energimæssige forhold (fx potentielle høje energiomkostninger)
- Bygningsmæssige forhold (alder, potentielle skjulte fejl, vedligeholdelsesbehov)
- Beliggenhed (støj, trafik, kommende byggeri, parkering)
- Økonomiske forhold (løbende udgifter, boligudgift sammenlignet med markedet)
- Juridiske forhold (forpligtelser, vedtægter, husdyr, udlejning)


**RISICI:**
Identificér mindst 8 risici ved boligen baseret på den givne tekst. Brug din ekspertise til at:
- Vurdere sandsynlige risici baseret på boligtype, alder, beliggenhed og andre tilgængelige oplysninger.
- Komme med realistiske og relevante antagelser, fx om potentielle omkostninger, støjgener eller renoveringsbehov.
- Angive konkrete anbefalinger til spørgsmål, som køberen bør stille eller områder, der bør undersøges yderligere.
- En risiko må ikke involvere energi mærkning, hvis energi mærkningen mangler.


**FORDELE:**
Identificér mindst 8 fordele, der realistisk kan udledes af teksten. Brug din faglige dømmekraft og understreg styrker, der kan give værdi for køberen.

** Boligannonce: **
{text_content}


4. Returnér svaret i nedenstående JSON-format:

Hvis Energi Mærkningen mangler, er det pågrund af en system fejl, du skal derfor ikke kommentere på det, og blot svare
"Se hos mægler".

**VIGTIGT:** Dit svar SKAL være et JSON-objekt, der følger den specificerede struktur nedenfor. Inkluder IKKE nogen tekst før eller efter JSON-objektet. Start direkte med `{{` og slut direkte med `}}`.

{{
  "summary": "Dine vigtigste konklusioner fra din grundige analyse af kommunen, lokalområdet, og boligopslaget",
  "property": {{
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
  }},
  "risks": [
    {{
      "category": "Energi|Tilstand|Økonomi|Beliggenhed|Juridisk|Andet",
      "title": "Kort, præcis titel på risiko",
      "details": "Grundig vurdering af risikoen (2-3 sætninger)",
      "excerpt": "Relevante tekstdetaljer eller din egen vurdering",
      "recommendations": [
        {{"promptTitle": "Spørg mægler/Undersøg nærmere", "prompt": "Relevant spørgsmål, der bør stilles mægleren"}}
      ]
    }}
  ],
  "highlights": [
    {{
      "icon": "home|building|map|key|piggy-bank|scale|star|heart|award|lightbulb|thumbs-up|check|flag|search",
      "title": "Kort præcis fordel",
      "details": "Begrundet forklaring af fordelen (2-3 sætninger)"
    }}
  ]
}}
"""

    def _extract_json_from_response(self, raw_text: str) -> Dict[str, Any]:
        """Extracts the JSON object from Claude's final response text."""
        try:
            # Find the start and end of the JSON object, assuming it's the main content
            json_start = raw_text.find("{")
            json_end = raw_text.rfind("}")

            if json_start == -1 or json_end == -1:
                logger.error(f"Could not find JSON object in response: {raw_text}")
                # Attempt to find JSON within ```json ... ``` blocks as a fallback
                json_block_start = raw_text.find("```json")
                if json_block_start != -1:
                    json_start = raw_text.find("{", json_block_start)
                    json_end = raw_text.rfind("}", json_start)
                    if json_start != -1 and json_end != -1:
                         json_text = raw_text[json_start : json_end + 1]
                         logger.warning("Found JSON within ```json block after initial failure.")
                         return json.loads(json_text)

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

    async def _make_claude_request(
        self,
        messages: List[MessageParam],
        tools: List[Dict[str, Any]],
        retry_count: int = 0
    ) -> Message:
        """Makes a request to the Claude API, handling retries for rate limits."""
        try:
            # logger.debug(f"Claude Request - Messages: {json.dumps(messages, indent=2)}")
            # logger.debug(f"Claude Request - Tools: {json.dumps(tools, indent=2)}")
            message_response = await self.client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=CLAUDE_MAX_TOKENS,
                temperature=CLAUDE_TEMPERATURE,
                messages=messages,
                tools=tools,
                # headers={ # Usually handled by the library
                #     "anthropic-version": ANTHROPIC_VERSION_HEADER,
                #     "anthropic-beta": ANTHROPIC_BETA_HEADER
                # }
            )
            # logger.debug(f"Claude Raw Response: {message_response}")
            return message_response

        except anthropic.RateLimitError as e:
            if retry_count < MAX_RETRIES:
                logger.warning(f"Rate limit exceeded. Retrying in {RETRY_DELAY_SECONDS}s... (Attempt {retry_count + 1}/{MAX_RETRIES})")
                await asyncio.sleep(RETRY_DELAY_SECONDS)
                return await self._make_claude_request(messages, tools, retry_count + 1)
            else:
                logger.error(f"Rate limit exceeded after {MAX_RETRIES} retries.", exc_info=True)
                raise RuntimeError("AI service rate limit exceeded after multiple retries.") from e
        except anthropic.APIConnectionError as e:
            logger.error(f"Anthropic API connection error: {e}", exc_info=True)
            raise RuntimeError("Failed to connect to AI service.") from e
        except anthropic.APIStatusError as e:
            logger.error(f"Anthropic API status error: {e.status_code} - {e.response}", exc_info=True)
            raise RuntimeError(f"AI service returned an error (Status {e.status_code}).") from e
        except Exception as e:
            logger.error(f"Unexpected error during Claude API call: {e}", exc_info=True)
            raise RuntimeError("An unexpected error occurred during AI analysis.") from e


    async def analyze_with_tools(self, initial_prompt: str) -> Dict[str, Any]:
        """
        Analyzes text using Claude API with a tool calling loop.

        Args:
            initial_prompt: The initial user prompt for the analysis.

        Returns:
            A dictionary representing the structured analysis result (JSON).
        """
        logger.info("Starting AI analysis with tool calling.")
        if not self.client:
             raise RuntimeError("Anthropic client not initialized.")

        tools = self.tool_registry.get_tool_definitions()
        messages: List[MessageParam] = [{"role": "user", "content": initial_prompt}]
        final_text_response = ""

        while True:
            logger.info(f"Calling Claude API. Message count: {len(messages)}")
            response: Message = await self._make_claude_request(messages, tools)

            # Append the assistant's response message to the history
            # We need to construct the dictionary representation expected by the API
            assistant_response_content: List[Union[Dict[str, Any], ContentBlock]] = []
            if response.content:
                # Convert Pydantic models back to dicts for the next API call if needed
                # The library might handle this automatically, but being explicit can help debugging
                for block in response.content:
                    if hasattr(block, 'text'):
                        assistant_response_content.append({"type": "text", "text": block.text})
                    elif hasattr(block, 'name') and hasattr(block, 'input'):
                        assistant_response_content.append({
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.input
                        })

            if assistant_response_content: # Only append if there's content
                messages.append({"role": "assistant", "content": assistant_response_content})

            # Process the response blocks
            tool_calls_requested = False
            tool_results_content: List[Dict[str, Any]] = [] # Content for the next user message

            for block in response.content:
                if hasattr(block, 'text'):
                    logger.debug(f"Received text block: {block.text[:100]}...")
                    final_text_response += block.text # Accumulate text responses

                elif hasattr(block, 'name') and hasattr(block, 'input'):
                    tool_calls_requested = True
                    tool_name = block.name
                    tool_input = block.input
                    tool_call_id = block.id
                    logger.info(f"AI requested tool call: {tool_name} with ID: {tool_call_id}")

                    tool_request = ToolCallRequest(tool_name=tool_name, parameters=tool_input)

                    try:
                        tool_response: ToolCallResponse = await self.tool_registry.execute_tool(tool_request)
                        tool_result_str = ""
                        if tool_response.error:
                            logger.error(f"Error executing tool {tool_name}: {tool_response.error}")
                            tool_result_str = json.dumps({"error": tool_response.error})
                            # Append error result
                            tool_results_content.append({
                                "type": "tool_result",
                                "tool_use_id": tool_call_id,
                                "content": tool_result_str,
                                "is_error": True # Explicitly mark as error
                            })
                        else:
                            # Claude expects the tool result content as a string.
                            # If the result is complex (e.g., dict/list), serialize it.
                            if isinstance(tool_response.result, (dict, list)):
                                tool_result_str = json.dumps(tool_response.result)
                            elif isinstance(tool_response.result, str):
                                tool_result_str = tool_response.result
                            else:
                                tool_result_str = str(tool_response.result) # Fallback

                            logger.info(f"Tool {tool_name} executed successfully.")
                            # Append success result
                            tool_results_content.append({
                                "type": "tool_result",
                                "tool_use_id": tool_call_id,
                                "content": tool_result_str
                            })

                    except Exception as e:
                        logger.error(f"Unexpected error executing tool {tool_name}: {e}", exc_info=True)
                        error_content = json.dumps({"error": f"Failed to execute tool {tool_name}: {str(e)}"})
                        # Append unexpected error result
                        tool_results_content.append({
                            "type": "tool_result",
                            "tool_use_id": tool_call_id,
                            "content": error_content,
                            "is_error": True
                        })

            # If no tool calls were requested in this turn, we're done.
            if not tool_calls_requested:
                logger.info("No tool calls requested by AI. Finishing analysis.")
                break

            # If tools were called, add a user message with the results and continue loop
            if tool_results_content:
                messages.append({"role": "user", "content": tool_results_content})
            else:
                # Should not happen if tool_calls_requested was True, but handle defensively
                logger.warning("Tool calls were requested, but no results were generated. Breaking loop.")
                break

        # After the loop, extract the final JSON from the accumulated text response
        logger.info("AI analysis loop finished. Extracting final JSON.")
        if not final_text_response:
             # Handle cases where the AI might *only* respond with tool calls initially
             # and the final response might be in the last assistant message without tool calls.
             last_message = messages[-1] if messages else {}
             if last_message.get("role") == "assistant":
                 for block_dict in last_message.get("content", []):
                     if block_dict.get("type") == "text":
                         final_text_response += block_dict.get("text", "")

        if not final_text_response:
            logger.error("No final text response received from AI after tool interactions.")
            raise RuntimeError("AI analysis completed without providing a final text response.")

        analysis_json = self._extract_json_from_response(final_text_response)

        # Optional: Validate the extracted JSON against Pydantic schema
        try:
            _ = AnalysisResultData(**analysis_json) # Validate structure
            logger.info("AI analysis JSON successfully validated against schema.")
        except Exception as e: # Catch Pydantic ValidationError specifically if needed
            logger.warning(f"AI response JSON failed validation against AnalysisResultData schema: {e}")
            # Return the unvalidated JSON but log warning.
            pass

        return analysis_json


    async def analyze_text(self, text_content: str) -> Dict[str, Any]:
        """
        Analyzes the provided text content using the Claude API with tool calling.
        This is the main entry point for single text analysis.

        Args:
            text_content: The text extracted from the listing page.

        Returns:
            A dictionary representing the structured analysis result.

        Raises:
            ValueError: If text_content is empty.
            RuntimeError: If the analysis process fails.
        """
        logger.info(f"Received request to analyze text (length: {len(text_content)})")
        if not text_content:
            raise ValueError("No text content provided for analysis.")

        # Create the initial prompt using the potentially updated method
        prompt = self._create_analysis_prompt(text_content)

        # Call the new method that handles the tool calling loop
        return await self.analyze_with_tools(prompt)

    async def analyze_multiple_texts(
        self,
        primary_text: str,
        secondary_text: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyzes combined primary and secondary text content.

        Args:
            primary_text: The main text content (e.g., from the listing page).
            secondary_text: Optional additional text (e.g., from realtor page).

        Returns:
            A dictionary representing the structured analysis result.
        """
        logger.info("Received request to analyze multiple texts.")
        combined_text = primary_text
        if secondary_text:
            logger.info("Combining primary and secondary text.")
            combined_text += "\n\n--- Additional Information ---\n\n" + secondary_text

        # Call the main analysis method with the combined text
        return await self.analyze_text(combined_text)