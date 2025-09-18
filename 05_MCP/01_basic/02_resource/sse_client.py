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
        self.resource = {}

    async def run(self, query: str):
        read_stream, write_stream = await self.exit_stack.enter_async_context(sse_client(self.server_path))
        session = await self.exit_stack.enter_async_context(
            ClientSession(read_stream=read_stream, write_stream=write_stream))
        await session.initialize()

        resources = (await session.list_resources()).resources
        functions = []
        for resource in resources:
            uri = resource.uri
            name = resource.name
            description = resource.description
            mime_type = resource.mimeType
            self.resource[name] = {
                "uri": uri,
                "name": name,
                "description": description,
                "mime_type": mime_type
            }
            functions.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "input_schema": None
                }
            })
        messages = [{
            "role": "user",
            "content": query
        }]
        deepseek_choice = self.deepseek.chat.completions.create(
            messages=messages,
            model="deepseek-chat",
            tools=functions
        ).choices[0]

        if deepseek_choice.finish_reason == "tool_calls":
            messages.append(deepseek_choice.message.model_dump())

            tool_calls = deepseek_choice.message.tool_calls
            for tool_call in tool_calls:
                tool_call_id = tool_call.id
                function = tool_call.function
                function_name = function.name
                function_arguments = function.arguments
                uri = self.resource[function_name]["uri"]

                # 调用resource内容
                resource_response = (await session.read_resource(uri=uri)).contents[0].text
                messages.append({
                    "role": "tool",
                    "content": resource_response,
                    "tool_call_id": tool_call_id
                })

            response = self.deepseek.chat.completions.create(
                model='deepseek-chat',
                messages=messages
            )
            print(f"AI综合MCP答复的回答：{response.choices[0].message.content}")
        else:
            print("无可用MCP资源，拒绝回答")


async def main(server_path, query):
    client = MCPClient(server_path=server_path)
    try:
        await client.run(query=query)
    finally:
        await client.exit_stack.aclose()


if __name__ == '__main__':
     asyncio.run(main(server_path="http://127.0.0.1:8000/sse", query="查找知鸟课堂的信息"))
     # asyncio.run(main(server_path="http://127.0.0.1:8000/sse", query="查找钢铁侠的信息"))

'''
tool_call 的格式：
ChatCompletionMessageFunctionToolCall(id='call_00_3S4G9gOW8eCmtPtFJuKUA9CT', function=Function(arguments='{}', name='zhiliao_file'), type='function', index=0)


resource的response内容
meta=None contents=[TextResourceContents(uri=AnyUrl('file://zhiliao.txt/'), mimeType='text/plain', meta=None, text='xx')]

'''