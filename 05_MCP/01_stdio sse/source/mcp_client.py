from mcp.client.sse import sse_client
from mcp import ClientSession
from openai import OpenAI
from contextlib import AsyncExitStack
import asyncio,os


class MCPClient:
    def __init__(self):
        self.deepseek = OpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com"
        )
        self.exit_stack = AsyncExitStack()
        self.resources = {}

    async def run(self, query):
        # 1. 创建read_stream、write_stream
        read_stream, write_stream = await self.exit_stack.enter_async_context(sse_client(url="http://127.0.0.1:8000/sse"))
        # 2. 创建session对象
        session: ClientSession = await self.exit_stack.enter_async_context(ClientSession(read_stream, write_stream))

        # 3. 初始化
        await session.initialize()

        functions = []
        # 获取服务端提供的所有resource
        resources = (await session.list_resources()).resources
        for resource in resources:
            uri = resource.uri
            name = resource.name
            description = resource.description
            mime_type = resource.mimeType
            self.resources[name] = {
                "uri": uri,
                "name": name,
                "description": description,
                "mime_type": mime_type,
            }
            # Function Calling的函数格式
            functions.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    # 资源类型，input_schema设置为None
                    "input_schema": None
                }
            })

        # 创建消息发送给大模型
        messages = [{
            "role": "user",
            "content": query
        }]
        deepseek_response = self.deepseek.chat.completions.create(
            messages=messages,
            model="deepseek-chat",
            tools=functions
        )
        model_choice = deepseek_response.choices[0]
        # 如果大模型的回复是tool_calls，那么我们就要执行调用工具的代码
        if model_choice.finish_reason == 'tool_calls':
            # 为了让大模型能够更加精准的回复，需要将大模型返回回来的message也添加到messages中
            model_message = model_choice.message
            # message.model_dump：pydantic库提供的方法，model_message是pydantic的BaseModel的子类对象
            # model_dump是将Model对象上的属性转换为字典
            messages.append(model_message.model_dump())

            tool_calls = model_message.tool_calls
            for tool_call in tool_calls:
                tool_call_id = tool_call.id
                function = tool_call.function
                function_arguments = function.arguments
                function_name = function.name
                uri = self.resources[function_name]["uri"]
                # 执行调用，response是MCP Server返回回来的
                response = await session.read_resource(uri)
                result = response.contents[0].text
                # 把result丢给大模型，让大模型生成最终的结果
                messages.append({
                    "role": "tool",
                    "content": result,
                    "tool_call_id": tool_call_id
                })
                model_response = self.deepseek.chat.completions.create(
                    model="deepseek-chat",
                    messages=messages
                )
                print(model_response.choices[0].message.content)




    async def aclose(self):
        await self.exit_stack.aclose()


async def main():
    client = MCPClient()
    try:
        await client.run("帮我查找一下知了课堂的相关信息")
    finally:
        await client.aclose()


if __name__ == '__main__':
    asyncio.run(main())