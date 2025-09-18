from openai import OpenAI
from mcp.client.sse import sse_client
from mcp import ClientSession
import asyncio
from contextlib import AsyncExitStack
from mcp.types import PromptMessage
import json
from mcp.types import PromptArgument
import json,os, dotenv

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

    async def run(self, query: str):
        read_stream, write_stream = await self.exit_stack.enter_async_context(sse_client(self.server_path))
        session = await self.exit_stack.enter_async_context(
            ClientSession(read_stream=read_stream, write_stream=write_stream))
        await session.initialize()

        prompts = (await session.list_prompts()).prompts
        functions = []
        for prompt in prompts:
            name = prompt.name,
            description = prompt.description,
            arguments = prompt.arguments
            functions.append({
                "type": "function",
                "function": {
                    "name": name[0],
                    "description": description[0],
                    "input_schema": None
                }
            })
            self.prompts[name] = {
                "name": name[0],
                "description": description[0],
                "arguments": [arg.model_dump() for arg in arguments] if arguments else []
            }

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

            # 获取工具
            tool_calls = deepseek_choice.message.tool_calls
            for tool_call in tool_calls:
                tool_call_id= tool_call.id
                function = tool_call.function
                function_name = function.name
                function_arguments = json.loads(function.arguments)

                prompt_response = (await session.get_prompt(
                    name=function_name,
                    arguments=function_arguments
                ))
                prompt_message: PromptMessage = prompt_response.messages[0]

                messages.append({
                    "role":"tool",
                    "content": prompt_message.content.text,
                    "tool_call_id": tool_call_id
                })
                model_response = self.deepseek.chat.completions.create(
                    messages=messages,
                    model="deepseek-chat"
                )
                print(model_response.choices[0].message.content)


async def main(server_path):
    client = MCPClient(server_path=server_path)
    try:
        with open("/Users/kevin/Library/Mobile Documents/com~apple~CloudDocs/AGI/05_MCP/01_basic/04_prompt/data/policy.txt", mode="r", encoding="utf-8") as fp:
            policy = fp.read()
        await client.run(query=f"总结这个政策：{policy}")
    finally:
        await client.exit_stack.aclose()


if __name__ == '__main__':
    asyncio.run(main(server_path="http://127.0.0.1:8000/sse"))


'''
prompts格式
[Prompt(name='policy_prompt', title=None, description='\n能够对用户提供的政策内容，对其进行总结、提取关键信息的提示词模板\n:param policy: 需要总结的政策内容\n:return: 总结政策的提示词模板\n', arguments=[PromptArgument(name='policy', description=None, required=True)], meta=None)]


messages
[{'role': 'user', 'content': '总结这个政策：xxx'}, {'content': '我来帮您总结这个政策文件。让我使用政策分析工具来处理这个内容。', 'refusal': None, 'role': 'assistant', 'annotations': None, 'audio': None, 'function_call': None, 'tool_calls': [{'id': 'call_00_J3kNnAtoeh894QdjwVWYhi4E', 'function': {'arguments': '{"policy": "xxxx"}', 'name': 'policy_prompt'}, 'type': 'function', 'index': 0}]}, {'role': 'tool', 'content': '\n        这个是政策内容：“xxx”，请对该政策内容进行总结，总结的规则为：\n        1. 提取政策要点。\n        2. 针对每个政策要点按照以下格式进行总结：\n            * 要点标题：政策的标题，要包含具体的政策信息\n            * 针对人群：政策针对的人群\n            * 有效时间：政策执行的开始时间和结束时间\n            * 相关部门：政策是由哪些部门执行\n        总结的内容不要太官方，用通俗易懂的语言。\n        ', 'tool_call_id': 'call_00_J3kNnAtoeh894QdjwVWYhi4E'}]

'''








