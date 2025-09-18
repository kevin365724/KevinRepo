#!/usr/bin/env python3
# -*- coding:utf-8 -*-
# sse_client.py
# @time:2025/9/15/23:05

from openai import OpenAI
from mcp.client.sse import sse_client
from mcp import ClientSession
from contextlib import AsyncExitStack
from mcp.shared.context import RequestContext
from mcp.types import CreateMessageRequestParams, CreateMessageResult, TextContent
from typing import Any
import json, os, dotenv, asyncio

dotenv.load_dotenv()

class MCPClient():
    def __init__(self, server_path: str):
        self.server_path = server_path
        self.deepseek = OpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com"
        )
        self.exit_stack = AsyncExitStack()
        self.prompts = {}

    async def sampling_handler(
            self,
            context: RequestContext["ClientSession", Any],
            params: CreateMessageRequestParams,
    ) -> CreateMessageResult:
        print(f"context: {context}")
        print(f"params: {params}")
        message = params.messages[0]
        messages = [{
            "role": message.role,
            "content": message.content.text
        }]

        message = self.deepseek.chat.completions.create(
            messages = messages,
            model="deepseek-chat",
        ).choices[0].message
        return CreateMessageResult(
            role="assistant",
            content=TextContent(text=message.content, type="text"),
            model="deepseek-chat"
        )

    async def run(self):
        read_stream, write_stream = await self.exit_stack.enter_async_context(sse_client(self.server_path))
        session = await self.exit_stack.enter_async_context(
            ClientSession(read_stream=read_stream,
                          write_stream=write_stream,
                          sampling_callback=self.sampling_handler
                          ))
        await session.initialize()

        tools = (await session.list_tools()).tools
        for tool in tools:
            response = await session.call_tool(name=tool.name)
            print(response)

async def main(server_path):
    client = MCPClient(server_path=server_path)
    try:
        await client.run()
    finally:
        await client.exit_stack.aclose()



if __name__ == '__main__':
    asyncio.run(main(server_path="http://127.0.0.1:8000/sse"))