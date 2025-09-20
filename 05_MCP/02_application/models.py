      
from pydantic import BaseModel
from enum import Enum
from typing import Any
from mcp.types import AnyUrl, PromptArgument

class MCPFunctionType(Enum):
    TOOL = "tool"
    RESOURCE = "resource"
    RESOURCE_TEMPLATE = "resource_template"
    PROMPT = "prompt"


class MCPFunction(BaseModel):
    name: str
    origin_name: str
    server_name: str
    description: str
    type_: MCPFunctionType
    # input_schema：是Tool独有的属性
    input_schema: dict[str, Any] | None = None
    # uri：是Resource/Resource Template独有的属性
    uri: str | AnyUrl | None = None
    # arguments：是prompt独有的属性
    arguments: list[PromptArgument] | None = None

    