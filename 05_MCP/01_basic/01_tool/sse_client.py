from openai import OpenAI
from mcp.client.sse import sse_client
from mcp import ClientSession
from contextlib import AsyncExitStack
import os, dotenv, asyncio, json

dotenv.load_dotenv()

class MCPClient():
    def __init__(self, server_path: str):
        self.server_path = server_path
        self.deepseek = OpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com"
        )
        self.exit_stack = AsyncExitStack()

    async def run(self, query: str):
        # 1. 创建连接服务端的参数
        read_stream, write_stream = await self.exit_stack.enter_async_context(sse_client(self.server_path))
        session = await self.exit_stack.enter_async_context(ClientSession(read_stream=read_stream, write_stream=write_stream))

        # 2. 初始化通信
        await session.initialize()

        # 3. 获取服务端有的tools
        response = await session.list_tools()
        # 4. 将工具封装成Function Calling格式的对象
        tools = []
        for tool in response.tools:
            name = tool.name
            description = tool.description
            input_schema = tool.inputSchema
            tools.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "input_schema": input_schema,
                }
            })
        # 5. 发送消息给大模型，让大模型自主选择哪个工具（大模型不会自己调用）
        messages = [{
            "role": "user",
            "content": query
        }]
        deepseek_choice = self.deepseek.chat.completions.create(
            messages=messages,
            model="deepseek-chat",
            tools=tools
        ).choices[0]

        if deepseek_choice.finish_reason == "tool_calls":
            messages.append(deepseek_choice.message.model_dump())

            # 获取工具
            tool_calls = deepseek_choice.message.tool_calls
            for tool_call in tool_calls:
                tool_call_id= tool_call.id
                function = tool_call.function
                function_name = function.name
                function_arguments = json.loads(function.arguments)
                # 调用工具
                tool_response = (await session.call_tool(
                    name=function_name,
                    arguments=function_arguments
                )).content[0]

                # 把工具调用的结果，添加到messages中
                messages.append({
                    "role": "tool",
                    "content": tool_response.text,
                    "tool_call_id": tool_call_id
                })

            # 重新由大模型根据MCP的结果进行回复
            response = self.deepseek.chat.completions.create(
                model='deepseek-chat',
                messages=messages
            )
            print(f"AI综合MCP答复的回答：{response.choices[0].message.content}")
        else:
            print("无可用MCP工具，拒绝回答")


async def main(server_path, query):
    client = MCPClient(server_path=server_path)
    try:
        await client.run(query=query)
    finally:
        await client.exit_stack.aclose()


if __name__ == '__main__':
     # asyncio.run(main(server_path="http://127.0.0.1:8000/sse",query= "请你计算一下 12 + 34 = ?"))
     asyncio.run(main(server_path="http://127.0.0.1:8000/sse", query="请你计算一下 12 的8次方= ?"))