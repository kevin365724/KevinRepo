      
# 用来存放一些和服务器交互的类
from enum import Enum
from typing import Any
from mcp.client.stdio import stdio_client, StdioServerParameters
from contextlib import AsyncExitStack
from mcp.client.session import ClientSession
from models import MCPFunction, MCPFunctionType
import asyncio
from mcp.shared.exceptions import McpError
from mcp.types import AnyUrl
from mcp.client.sse import sse_client


class MCPTransport(Enum):
    STDIO = "stdio"
    SSE = "sse"


class MCPServer:
    """
    这个类，代表的是一个MCP Server，里面封装了和MCP Server的连接、通信等
    """
    def __init__(
        self,
        name: str,
        transport: MCPTransport=MCPTransport.STDIO,
        cmd: str | None = None,
        args: list[str] | None = None,
        env: dict[str, Any] | None = None,
        url: str | None = None,
    ):
        self.name = name
        self.transport = transport
        if self.transport == MCPTransport.STDIO:
            assert cmd is not None
            assert args is not None
            self.cmd = cmd
            self.args = args
            self.env = env
        else:
            assert url is not None
            self.url = url

        # 异步上下文堆栈
        self._exit_stack = AsyncExitStack()
        # 与服务器通话的session对象
        self.session: ClientSession | None = None
        # 保存当前MCP Server的所有Function（Tool、Resource、Resource Template、 Prompt）
        self.functions: dict[str, MCPFunction] = {}

    async def initialize(self):
        # 初始化操作：连接好MCP Server，以及获取Session对象，以及服务的Tool、Resource、Prompt
        if self.transport == MCPTransport.STDIO:
            params = StdioServerParameters(
                command = self.cmd,
                args = self.args,
                env = self.env,
            )
            read_stream, write_stream = await self._exit_stack.enter_async_context(
                stdio_client(params)
            )
            self.session = await self._exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
        else:
            read_stream, write_stream = await self._exit_stack.enter_async_context(
                # url: http://127.0.0.1:8000/sse
                sse_client(self.url)
            )
            self.session = await self._exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )

        # 要初始化
        await self.session.initialize()
        # 获取MCP Server的所有Tool、Resource、Prompt
        await self.fetch_functions()

    async def fetch_functions(self):
        assert self.session is not None
        # 1. 获取tool
        try:
            tools = (await self.session.list_tools()).tools
        except McpError:
            tools = []
        for tool in tools:
            tool_name = tool.name.replace(" ", "_")
            self.functions[tool_name] = MCPFunction(
                name=tool_name,
                origin_name=tool.name,
                server_name=self.name,
                description=tool.description,
                type_=MCPFunctionType.TOOL,
                input_schema=tool.inputSchema
            )
        # 2. 获取resource
        try:
            resources = (await self.session.list_resources()).resources
        except McpError:
            resources = []
        for resource in resources:
            resource_name = resource.name.replace(" ", "_")
            self.functions[resource_name] = MCPFunction(
                name=resource_name,
                origin_name=resource.name,
                server_name=self.name,
                description=resource.description,
                type_=MCPFunctionType.RESOURCE,
                # 如果是Resource类型，那么resource.uri是AnyUrl类型
                uri=resource.uri
            )
        # 3. 获取resource template
        try:
            resource_templates = (await self.session.list_resource_templates()).resourceTemplates
        except McpError:
            resource_templates = []
        for resource_template in resource_templates:
            resource_template_name = resource_template.name.replace(" ", "_")
            self.functions[resource_template_name] = MCPFunction(
                name=resource_template_name,
                origin_name=resource_template.name,
                server_name=self.name,
                description=resource_template.description,
                type_=MCPFunctionType.RESOURCE_TEMPLATE,
                # 如果是RESOURCE_TEMPLATE类型，那么uriTemplate是str类型
                uri=resource_template.uriTemplate
            )
        # 4. 获取prompt
        try:
            prompts = (await self.session.list_prompts()).prompts
        except McpError:
            prompts = []
        for prompt in prompts:
            # print(type(prompt.arguments))
            # print(type(prompt.arguments[0]))
            # print(prompt.arguments)
            prompt_name = prompt.name.replace(" ", "_")
            self.functions[prompt_name] = MCPFunction(
                name=prompt_name,
                origin_name=prompt.name,
                server_name=self.name,
                description=prompt.description,
                type_=MCPFunctionType.PROMPT,
                arguments=prompt.arguments
            )

    async def call_function(self, name: str, arguments: dict[str, Any] | None = None):
        function = self.functions[name]
        if function.type_ == MCPFunctionType.TOOL:
            response = await self.session.call_tool(name=function.origin_name, arguments=arguments)
            return response.content[0].text
        elif function.type_ == MCPFunctionType.RESOURCE:
            response = await self.session.read_resource(function.uri)
            return response.contents[0].text
        elif function.type_ == MCPFunctionType.RESOURCE_TEMPLATE:
            # resource_template类型：需要将参数格式化到uri中
            # uri：file://{filename}.format(filename=xxx)
            uri = AnyUrl(function.uri.format(**arguments))
            response = await self.session.read_resource(uri)
            return response.contents[0].text
        else:
            response = await self.session.get_prompt(name=function.origin_name, arguments=arguments)
            return response.content.text

    async def aclose(self):
        await self._exit_stack.aclose()

    async def __aenter__(self):
        # 初始化
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.aclose()


class MCPServerManager:
    def __init__(self, mcp_dicts: dict):
        self.mcp_dicts = mcp_dicts
        self.servers: dict[str,MCPServer] = {}
        self._exit_stack: AsyncExitStack = AsyncExitStack()
        self.all_functions: dict[str, MCPFunction] = {}

    async def initialize(self):
        for name, mcp_dict in self.mcp_dicts.items():
            # 1. 创建好所有的MCP Server对象
            transport = MCPTransport.STDIO
            if not mcp_dict.get('command'):
                transport = MCPTransport.SSE
            server = await self._exit_stack.enter_async_context(
                MCPServer(
                    name=name,
                    transport=transport,
                    cmd=mcp_dict.get('command'),
                    args=mcp_dict.get('args'),
                    env=mcp_dict.get('env'),
                    url=mcp_dict.get('url')
                )
            )
            self.servers[name] = server
            # 2. 获取所有MCP Server的函数并且保存起来，也是存储成字典形式
            self.all_functions.update(server.functions)

    async def call_function(self, name: str, arguments: dict[str, Any]|None=None):
        function = self.all_functions[name]
        server = self.servers[function.server_name]
        return await server.call_function(name, arguments=arguments)

    async def aclose(self):
        await self._exit_stack.aclose()

    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.aclose()


async def main1():
    server = MCPServer(
        name="filesystem",
        cmd="npx",
        args=['-y', '@modelcontextprotocol/server-filesystem', "/Users/kevin/Desktop"]
    )
    await server.initialize()
    result = await server.call_function("read_file", {"path": "/Users/kevin/Desktop/test.txt"})
    print(result)
    await server.aclose()

async def main2():
    async with MCPServer(
        name="sqlite",
        cmd="uvx",
        args=['mcp-server-sqlite', '--db-path', "C:/Users/hynev/Desktop/db.sqlite"]
    ) as server:
        result = await server.call_function(name="Business Insights Memo")
        print(result)

async def main():
    exit_stack = AsyncExitStack()
    server = await exit_stack.enter_async_context(MCPServer(
        name="sqlite",
        cmd="uvx",
        args=['mcp-server-sqlite', '--db-path', "C:/Users/hynev/Desktop/db.sqlite"]
    ))
    result = await server.call_function(name="Business Insights Memo")
    print(result)
    await exit_stack.aclose()


if __name__ == '__main__':
    asyncio.run(main1())

    