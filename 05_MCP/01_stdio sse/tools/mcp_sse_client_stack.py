#!/usr/bin/env python3
# -*- coding:utf-8 -*-
# mcp_sse_serve.py
# @time:2025/9/9/23:18
from openai import OpenAI
import os
from mcp.client.sse import sse_client
from contextlib import AsyncExitStack
from mcp import ClientSession
import json
import asyncio




class MCPClient:
    def __init__(self, server_url: str):
        self.server_url = server_url
        self.deepseek = OpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com"
        )
        self.exit_stack = AsyncExitStack()

    async def run(self, query):
        # stacked context manager
        read_stream, write_stream = await self.exit_stack.enter_async_context(sse_client("http://127.0.0.1:8000/sse"))
        session: ClientSession = await self.exit_stack.enter_async_context(ClientSession(read_stream, write_stream))
        # 初始化
        await session.initialize()

        # 获取所有可用的工具
        response = await session.list_tools()
        tools = [{
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.inputSchema
            }
        } for tool in response.tools]

        # 构建消息
        messages = [{
            "role": "user",
            "content": query
        }]

        # 让大模型根据query选择工具
        deepseek_response = self.deepseek.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            tools=tools,
        )

        # 提取大模型的选择
        choice = deepseek_response.choices[0]
        # 判断大模型是否选择了工具
        if choice.finish_reason == 'tool_calls':
            # 将大模型选择了哪个工具函数添加到messages中，为下次回答添加上下文，提高响应精度
            messages.append(choice.message.model_dump())

            tool_call = choice.message.tool_calls[0]
            # 获取函数名字
            function_name = tool_call.function.name
            # 获取函数需要的参数
            function_args = json.loads(tool_call.function.arguments)

            # 调用工具函数
            result = await session.call_tool(name=function_name, arguments=function_args)

            # 将工具函数返回的结果，添加到messages中，然后重新交给大模型，让大模型结合数据回答
            messages.append({
                'role': 'tool',
                'content': result.content[0].text,
                "tool_call_id": tool_call.id
            })

            # 重新调用大模型
            deepseek_response = self.deepseek.chat.completions.create(
                model="deepseek-chat",
                messages=messages
            )
            # 返回最终结果
            print(f"执行结果为：{deepseek_response.choices[0].message.content}")
        else:
            print('执行失败！')

    async def aclose(self):
        await self.exit_stack.aclose()

async def main(query):
    client = MCPClient(server_url="http://127.0.0.1:8000/sse")
    try:
        result = await client.run(query)
    finally:
        await client.aclose()

if __name__ == '__main__':
    asyncio.run(main('帮我计算一下2加3等于多少'))