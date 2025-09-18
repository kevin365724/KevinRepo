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

        resources = (await session.list_resource_templates()).resourceTemplates

        functions = []
        for resource in resources:
            uri = resource.uriTemplate
            original_name = resource.name
            name = resource.name.replace(" ", "_")
            description = resource.description
            mime_type = resource.mimeType
            self.resource[name] = {
                "uri": uri,
                "original_name": original_name,
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
        print(functions)
        messages = [{
            "role": "user",
            "content": query
        }]
        deepseek_choice = self.deepseek.chat.completions.create(
            messages=messages,
            model="deepseek-chat",
            tools=functions
        ).choices[0]
        print(deepseek_choice)
        #
        if deepseek_choice.finish_reason == "tool_calls":
            messages.append(deepseek_choice.message.model_dump())

            tool_calls = deepseek_choice.message.tool_calls
            for tool_call in tool_calls:
                tool_call_id = tool_call.id
                function = tool_call.function
                function_name = function.name
                function_arguments = json.loads(function.arguments)
                uri = self.resource[function_name]["uri"]

                # 调用resource内容
                resource_response = (await session.read_resource(uri=uri.format(**function_arguments))).contents[0].text
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
     asyncio.run(main(server_path="http://127.0.0.1:8000/sse", query="查找3年级的成绩，并比较一下王二和张三的成绩"))
     # asyncio.run(main(server_path="http://127.0.0.1:8000/sse", query="查找钢铁侠的信息"))

'''

[{'type': 'function', 'function': {'name': 'grade_score', 'description': '这边提供了一个成绩查询的MCP resource，可以根据年级grade和姓名name，返回用户的详情信息。\n:param grade: 年级，必须返回高一、高二或高三。 \n:param name: 学生姓名', 'input_schema': None}}]


Choice(finish_reason='tool_calls', index=0, logprobs=None, message=ChatCompletionMessage(content='我来帮您查找二年级周超同学的成绩信息。', refusal=None, role='assistant', annotations=None, audio=None, function_call=None, tool_calls=[ChatCompletionMessageFunctionToolCall(id='call_00_2LOWnL9Sbk9o6zdc8J87GTc8', function=Function(arguments='{"grade": "高二", "name": "周超"}', name='grade_score'), type='function', index=0)]))

'''