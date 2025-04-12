from pydantic import BaseModel, Field, create_model
from typing import Dict, List, Optional, Any, Type, Literal

# Mapping from JSON Schema types to Python types
TYPE_MAP = {
    "string": str,
    "number": float, # Use float for broader compatibility (includes integers)
    "integer": int,
    "boolean": bool,
    "array": list,
    "object": dict,
}

class ToolProperty(BaseModel):
    """Describes a single property within the tool's input schema."""
    type: str = Field(..., description="The JSON schema type of the property (e.g., 'string', 'number').")
    description: Optional[str] = Field(None, description="A description of what the property represents.")
    enum: Optional[List[Any]] = Field(None, description="Optional list of allowed values for the property.")
    # Add other JSON schema fields as needed (e.g., format, items for arrays)

class ToolInputSchema(BaseModel):
    """Describes the input schema for a tool, following JSON Schema structure."""
    type: Literal["object"] = Field(default="object", description="The type of the schema, must be 'object'.")
    properties: Dict[str, ToolProperty] = Field(..., description="A dictionary mapping parameter names to their definitions.")
    required: List[str] = Field(default_factory=list, description="A list of parameter names that are required.")

    def get_pydantic_model(self) -> Optional[Type[BaseModel]]:
        """
        Dynamically creates a Pydantic model based on this schema definition.
        Used for validating input parameters.
        """
        fields = {}
        for name, prop in self.properties.items():
            python_type = TYPE_MAP.get(prop.type, Any) # Default to Any if type is unknown

            # Handle optional vs. required fields
            is_required = name in self.required
            field_default = ... if is_required else None # Ellipsis (...) marks required fields in Pydantic

            # Create field definition
            # For enums, we can use Literal if Pydantic version supports it well dynamically,
            # otherwise, validation might need custom logic or rely on standard type checks.
            # Simple approach for now: rely on type check and upstream validation for enum values.
            fields[name] = (python_type, Field(default=field_default, description=prop.description))

        if not fields:
            return None # No properties defined

        # Create the dynamic model
        model_name = "DynamicToolInputModel" # Name doesn't strictly matter here
        DynamicModel = create_model(model_name, **fields) # type: ignore
        return DynamicModel


class ToolDefinition(BaseModel):
    """Defines a tool that the AI can call."""
    name: str = Field(..., description="The unique name of the tool.")
    description: str = Field(..., description="A clear description of what the tool does and when to use it.")
    input_schema: ToolInputSchema = Field(..., description="The JSON schema defining the parameters the tool accepts.")


class ToolCallRequest(BaseModel):
    """Represents a request from the AI to call a specific tool."""
    tool_name: str = Field(..., description="The name of the tool to be called.")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="The parameters to pass to the tool, matching its input schema.")


class ToolCallResponse(BaseModel):
    """Represents the result or error after attempting to call a tool."""
    tool_name: str = Field(..., description="The name of the tool that was called.")
    result: Optional[Any] = Field(None, description="The result returned by the tool execution (if successful).")
    error: Optional[str] = Field(None, description="An error message if the tool execution failed.")