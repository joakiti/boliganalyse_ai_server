from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from pydantic import ValidationError

from src.app.schemas.tool_calling import ToolDefinition, ToolInputSchema

class BaseTool(ABC):
    """Abstract base class for all tools."""

    def __init__(self, definition: 'ToolDefinition'):
        """
        Initializes the tool with its definition.

        Args:
            definition: The Pydantic model representing the tool's definition.
        """
        if definition is None:
            raise ValueError("Tool definition cannot be None")
        self._definition = definition

    def get_definition(self) -> 'ToolDefinition':
        """
        Returns the tool's definition.

        Returns:
            The ToolDefinition object associated with this tool.
        """
        return self._definition

    def _validate_parameters(self, params: Dict[str, Any]):
        """
        Validates the input parameters against the tool's input schema.

        Args:
            params: The parameters provided for tool execution.

        Raises:
            ValueError: If validation fails (e.g., missing required fields, type mismatch).
        """
        schema_model = self._definition.input_schema.get_pydantic_model()
        if schema_model:
            try:
                # Pydantic automatically validates upon model instantiation
                schema_model(**params)
            except ValidationError as e:
                # Re-raise as a ValueError for consistent error handling upstream
                raise ValueError(f"Parameter validation failed: {e}")
        # If no schema_model, assume no validation needed or handled differently

    @abstractmethod
    async def execute(self, params: Dict[str, Any]) -> Any:
        """
        Executes the tool's logic with the given parameters.
        Subclasses must implement this method.

        Args:
            params: A dictionary containing the parameters for execution,
                    validated against the tool's input schema.

        Returns:
            The result of the tool's execution. The type depends on the tool.
        """
        pass # Subclasses must implement

# Note: The ToolDefinition structure is now defined in app.schemas.tool_calling