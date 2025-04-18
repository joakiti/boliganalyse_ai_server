import httpx
import json
from typing import Dict, Any, Optional, List, cast
from enum import Enum

from src.app.services.tools.base_tool import BaseTool
from src.app.schemas.tool_calling import ToolDefinition, ToolProperty, ToolInputSchema

DST_API_BASE_URL = "https://api.statbank.dk/v1"

# --- GetSubjectsTool ---

GET_SUBJECTS_TOOL_DEFINITION = ToolDefinition(
    name="get_dst_subjects",
    description="Retrieves subjects (categories) from the Danmarks Statistik (DST) API. Subjects can be hierarchical.",
    input_schema=ToolInputSchema(
        type="object",
        properties={
            "subjects": ToolProperty(
                type="array",
                description="Optional list of parent subject IDs to retrieve children for. If omitted, retrieves root subjects."
            ),
            "recursive": ToolProperty(
                type="boolean",
                description="If true, retrieves all descendants recursively. Defaults to false."
            ),
            "lang": ToolProperty(
                type="string",
                description="Language for the response (e.g., 'en', 'da'). Defaults to 'en'."
            )
        },
        required=[]
    )
)

class GetSubjectsTool(BaseTool):
    def __init__(self):
        super().__init__(GET_SUBJECTS_TOOL_DEFINITION)

    async def execute(self, params: Dict[str, Any]) -> str:
        """Executes the GetSubjectsTool to fetch subjects from DST API."""
        payload = {
            "subjects": params.get("subjects"),
            "recursive": params.get("recursive", False),
            "lang": params.get("lang", "en"),
            "format": "JSON" # Always request JSON for this tool
        }
        # Filter out keys with None values
        payload = {k: v for k, v in payload.items() if v is not None}

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{DST_API_BASE_URL}/subjects",
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                response.raise_for_status()  # Raise exception for 4xx or 5xx status codes
                return response.text # Return raw JSON string
            except httpx.HTTPStatusError as e:
                # Log error or handle specific status codes if needed
                return json.dumps({"error": f"DST API request failed: {e.response.status_code}", "details": e.response.text})
            except httpx.RequestError as e:
                return json.dumps({"error": f"DST API request failed: {str(e)}"})
            except Exception as e:
                # Catch unexpected errors
                return json.dumps({"error": f"An unexpected error occurred: {str(e)}"})

# --- GetTablesTool ---

GET_TABLES_TOOL_DEFINITION = ToolDefinition(
    name="get_dst_tables",
    description="Retrieves a list of tables from the Danmarks Statistik (DST) API, optionally filtered by subject and update recency.",
    input_schema=ToolInputSchema(
        type="object",
        properties={
            "subjects": ToolProperty(
                type="array",
                description="Optional list of subject IDs to filter tables by. If omitted, retrieves tables from all subjects."
            ),
            "pastDays": ToolProperty(
                type="integer",
                description="Optional number of days to look back for updated tables."
            ),
            "includeInactive": ToolProperty(
                type="boolean",
                description="If true, includes inactive tables in the result. Defaults to false."
            ),
            "lang": ToolProperty(
                type="string",
                description="Language for the response (e.g., 'en', 'da'). Defaults to 'en'."
            )
        },
        required=[]
    )
)

class GetTablesTool(BaseTool):
    def __init__(self):
        super().__init__(GET_TABLES_TOOL_DEFINITION)

    async def execute(self, params: Dict[str, Any]) -> str:
        """Executes the GetTablesTool to fetch tables from DST API."""
        payload = {
            "subjects": params.get("subjects"),
            "pastDays": params.get("pastDays"),
            "includeInactive": params.get("includeInactive", False),
            "lang": params.get("lang", "en"),
            "format": "JSON" # Always request JSON for this tool
        }
        # Filter out keys with None values
        payload = {k: v for k, v in payload.items() if v is not None}

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{DST_API_BASE_URL}/tables",
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                response.raise_for_status()
                return response.text # Return raw JSON string
            except httpx.HTTPStatusError as e:
                return json.dumps({"error": f"DST API request failed: {e.response.status_code}", "details": e.response.text})
            except httpx.RequestError as e:
                return json.dumps({"error": f"DST API request failed: {str(e)}"})
            except Exception as e:
                return json.dumps({"error": f"An unexpected error occurred: {str(e)}"})


# --- GetTableInfoTool ---

GET_TABLE_INFO_TOOL_DEFINITION = ToolDefinition(
    name="get_dst_table_info",
    description="Retrieves detailed metadata about a specific table from the Danmarks Statistik (DST) API, including variables, values, and time periods.",
    input_schema=ToolInputSchema(
        type="object",
        properties={
            "tableId": ToolProperty(
                type="string",
                description="The ID of the table to retrieve information for."
            ),
            "lang": ToolProperty(
                type="string",
                description="Language for the response (e.g., 'en', 'da'). Defaults to 'en'."
            )
        },
        required=["tableId"]
    )
)

class GetTableInfoTool(BaseTool):
    def __init__(self):
        super().__init__(GET_TABLE_INFO_TOOL_DEFINITION)

    async def execute(self, params: Dict[str, Any]) -> str:
        """Executes the GetTableInfoTool to fetch table metadata from DST API."""
        payload = {
            "table": params["tableId"],
            "lang": params.get("lang", "en"),
            "format": "JSON" # Always request JSON for this tool
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{DST_API_BASE_URL}/tableinfo",
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                response.raise_for_status()
                return response.text # Return raw JSON string
            except httpx.HTTPStatusError as e:
                return json.dumps({"error": f"DST API request failed: {e.response.status_code}", "details": e.response.text})
            except httpx.RequestError as e:
                return json.dumps({"error": f"DST API request failed: {str(e)}"})
            except Exception as e:
                return json.dumps({"error": f"An unexpected error occurred: {str(e)}"})


# --- GetDataTool ---

class DSTDataFormat(Enum):
    CSV = "CSV"
    XLSX = "XLSX"
    JSON = "JSON"
    JSONSTAT = "JSONSTAT"
    JSONSTAT2 = "JSONSTAT2"

GET_DATA_TOOL_DEFINITION = ToolDefinition(
    name="get_dst_data",
    description="Retrieves data from a specific table in the Danmarks Statistik (DST) API based on selected variables and values.",
    input_schema=ToolInputSchema(
        type="object",
        properties={
            "tableId": ToolProperty(
                type="string",
                description="The ID of the table to retrieve data from."
            ),
            "lang": ToolProperty(
                type="string",
                description="Language for the response (e.g., 'en', 'da'). Defaults to 'en'."
            ),
            "format": ToolProperty(
                type="string",
                description="The desired format for the data response.",
                enum=[f.value for f in DSTDataFormat]
            ),
            "variables": ToolProperty(
                type="array",
                description="An array specifying the variables and their selected values to include in the data retrieval."
            )
        },
        required=["tableId", "variables"]
    )
)

class GetDataTool(BaseTool):
    def __init__(self):
        super().__init__(GET_DATA_TOOL_DEFINITION)

    async def execute(self, params: Dict[str, Any]) -> str:
        """Executes the GetDataTool to fetch data from DST API."""
        data_format = params.get("format", DSTDataFormat.JSONSTAT.value)
        payload = {
            "table": params["tableId"],
            "format": data_format,
            "lang": params.get("lang", "en"),
            "variables": params["variables"]
        }
        # Filter out keys with None values
        payload = {k: v for k, v in payload.items() if v is not None}

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{DST_API_BASE_URL}/data",
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                response.raise_for_status()
                return response.text # Return raw JSON string
            except httpx.HTTPStatusError as e:
                return json.dumps({"error": f"DST API request failed: {e.response.status_code}", "details": e.response.text})
            except httpx.RequestError as e:
                return json.dumps({"error": f"DST API request failed: {str(e)}"})
            except Exception as e:
                return json.dumps({"error": f"An unexpected error occurred: {str(e)}"})