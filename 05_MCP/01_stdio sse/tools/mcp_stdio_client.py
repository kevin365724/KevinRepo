#!/usr/bin/env python3
# -*- coding:utf-8 -*-
# mcp_stdio_serve.py
# @time:2025/9/9/22:52
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp import ClientSession
# pip install openai
from openai import OpenAI
import asyncio
import json
from dotenv import load_dotenv
import os

load_dotenv()


class MCPClient:
    def __init__(self, server_path: str):
        self.deepseek = OpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com"
        )
        self.server_path = server_path


    async def run(self, query):
        server_params = StdioServerParameters(
            command="python",
            args=[self.server_path],
            env=None
        )
        async with stdio_client(server_params) as (read_stream, write_stream):
            # 创建和服务器通信的session对象
            async with ClientSession(read_stream=read_stream, write_stream=write_stream) as session:
                # 初始化
                await session.initialize()

                # 获取服务器支持函数
                response = await session.list_tools()

                # 将服务器提供的tool，封装成满足Function Calling的函数列表
                tools = [{
                    'type': 'function',
                    'function': {
                        'name': tool.name,
                        'description': tool.description,
                        'input_schema': tool.inputSchema
                    }
                } for tool in response.tools]

                # 给大模型构造消息
                messages = [{
                    'role': 'user',
                    'content': query,
                }]

                # 调用大模型，让大模型选择什么工具
                deepseek_response = self.deepseek.chat.completions.create(
                    model="deepseek-chat",
                    messages=messages,
                    tools=tools
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


if __name__ == '__main__':
    client = MCPClient("./tools/mcp_stdio_server.py")
    asyncio.run(client.run('帮我计算一下2加3等于多少'))