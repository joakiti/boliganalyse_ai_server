import logging
from typing import Dict, Any, Optional, List

from src.app.schemas.tool_calling import ToolDefinition, ToolCallRequest, ToolCallResponse
from src.app.services.tools.base_tool import BaseTool

logger = logging.getLogger(__name__)

# Schemas are now imported from app.schemas.tool_calling


class ToolRegistryService:
    """Manages the registration and execution of available tools."""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._definitions: Dict[str, 'ToolDefinition'] = {}
        logger.info("ToolRegistryService initialized.")

    def register_tool(self, tool: BaseTool):
        """
        Registers a tool instance and its definition.

        Args:
            tool: An instance of a class derived from BaseTool.
        """
        definition = tool.get_definition()
        tool_name = definition.name # Assuming ToolDefinition has a 'name' attribute
        if tool_name in self._tools:
            logger.warning(f"Tool '{tool_name}' is already registered. Overwriting.")
        self._tools[tool_name] = tool
        self._definitions[tool_name] = definition
        logger.info(f"Tool '{tool_name}' registered successfully.")

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """
        Retrieves a registered tool instance by its name.

        Args:
            name: The name of the tool.

        Returns:
            The BaseTool instance, or None if not found.
        """
        return self._tools.get(name)

    def get_tool_definition(self, name: str) -> Optional['ToolDefinition']:
        """
        Retrieves a registered tool definition by its name.

        Args:
            name: The name of the tool.

        Returns:
            The ToolDefinition object, or None if not found.
        """
        return self._definitions.get(name)

    def get_all_tool_definitions(self) -> List['ToolDefinition']:
        """
        Retrieves the definitions of all registered tools.

        Returns:
            A list of ToolDefinition objects.
        """
        return list(self._definitions.values())

    async def execute_tool(self, request: 'ToolCallRequest') -> 'ToolCallResponse':
        """
        Executes a registered tool based on the request.

        Args:
            request: A ToolCallRequest object containing the tool name and parameters.

        Returns:
            A ToolCallResponse object containing the result or an error message.
        """
        tool_name = request.tool_name
        params = request.parameters

        logger.info(f"Attempting to execute tool '{tool_name}' with params: {params}")

        tool = self.get_tool(tool_name)
        if not tool:
            error_msg = f"Tool '{tool_name}' not found."
            logger.error(error_msg)
            return ToolCallResponse(tool_name=tool_name, error=error_msg)

        try:
            # Validation is expected to happen within the tool's execute method
            # (or via _validate_parameters called by execute)
            result = await tool.execute(params=params)
            logger.info(f"Tool '{tool_name}' executed successfully.")
            return ToolCallResponse(tool_name=tool_name, result=result)
        except ValueError as ve:
            # Catch validation errors specifically
            error_msg = f"Error executing tool '{tool_name}': Validation failed - {ve}"
            logger.error(error_msg, exc_info=True)
            return ToolCallResponse(tool_name=tool_name, error=str(ve))
        except Exception as e:
            # Catch any other execution errors
            error_msg = f"An unexpected error occurred while executing tool '{tool_name}': {e}"
            logger.exception(error_msg) # Use logger.exception to include traceback
            return ToolCallResponse(tool_name=tool_name, error=f"Internal execution error: {e}")