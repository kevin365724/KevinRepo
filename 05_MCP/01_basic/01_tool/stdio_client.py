from openai import OpenAI
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp import ClientSession
from contextlib import AsyncExitStack
import os, dotenv, asyncio, json

dotenv.load_dotenv("/Users/kevin/Documents/.env")

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
        serve_parameter = StdioServerParameters(
            command="python",
            args=[self.server_path]
        )
        read_stream, write_stream = await self.exit_stack.enter_async_context(stdio_client(server=serve_parameter))
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


async def main(server_path,query):
    client = MCPClient(server_path=server_path)
    try:
        await client.run(query=query)
    finally:
        await client.exit_stack.aclose()


if __name__ == '__main__':
     asyncio.run(main(server_path="./stdio_server.py",query= "请你计算一下 12 + 34 = ?"))
     # asyncio.run(main(server_path="./stdio_server.py", query="请你计算一下 12 的8次方= ?"))

'''

session.list_tools()的返回结果
meta=None nextCursor=None tools=[Tool(name='plus_tool', title=None, description='\n    计算两数相加的工具\n    :param a: 第一个相加的数\n    :param b: 第二个相加的数\n    :return: 返回两数相加后的结果\n    ', inputSchema={'properties': {'a': {'title': 'A', 'type': 'number'}, 'b': {'title': 'B', 'type': 'number'}}, 'required': ['a', 'b'], 'title': 'plus_toolArguments', 'type': 'object'}, outputSchema={'properties': {'result': {'title': 'Result', 'type': 'number'}}, 'required': ['result'], 'title': 'plus_toolOutput', 'type': 'object'}, annotations=None, meta=None), Tool(name='minus_tool', title=None, description='\n    计算两数相减的工具\n    :param a: 被减数\n    :param b: 减数\n    :return: 返回两数相减后的结果\n    ', inputSchema={'properties': {'a': {'title': 'A', 'type': 'number'}, 'b': {'title': 'B', 'type': 'number'}}, 'required': ['a', 'b'], 'title': 'minus_toolArguments', 'type': 'object'}, outputSchema={'properties': {'result': {'title': 'Result', 'type': 'number'}}, 'required': ['result'], 'title': 'minus_toolOutput', 'type': 'object'}, annotations=None, meta=None)]


tools的格式
[
  {
    "type":"function",
    "function":{
      "name":"plus_tool",
      "description":"\n    计算两数相加的工具\n    :param a: 第一个相加的数\n    :param b: 第二个相加的数\n    :return: 返回两数相加后的结果\n    ",
      "input_schema":{
        "properties":{
          "a":{
            "title":"A",
            "type":"number"
          },
          "b":{
            "title":"B",
            "type":"number"
          }
        },
        "required":[
          "a",
          "b"
        ],
        "title":"plus_toolArguments",
        "type":"object"
      }
    }
  },
  {
    "type":"function",
    "function":{
      "name":"minus_tool",
      "description":"\n    计算两数相减的工具\n    :param a: 被减数\n    :param b: 减数\n    :return: 返回两数相减后的结果\n    ",
      "input_schema":{
        "properties":{
          "a":{
            "title":"A",
            "type":"number"
          },
          "b":{
            "title":"B",
            "type":"number"
          }
        },
        "required":[
          "a",
          "b"
        ],
        "title":"minus_toolArguments",
        "type":"object"
      }
    }
  }
]

deepseek_choice的内容
Choice(finish_reason='tool_calls', index=0, logprobs=None, message=ChatCompletionMessage(content='我来帮你计算 12 + 34。', refusal=None, role='assistant', annotations=None, audio=None, function_call=None, tool_calls=[ChatCompletionMessageFunctionToolCall(id='call_00_x9yO99dk2IKYnl7V4p7uw2eV', function=Function(arguments='{"a": 12, "b": 34}', name='plus_tool'), type='function', index=0)]))

deepseek_choice.message.model_dump()的内容
{'content': '我来帮你计算 12 + 34。', 'refusal': None, 'role': 'assistant', 'annotations': None, 'audio': None, 'function_call': None, 'tool_calls': [{'id': 'call_00_m0IhNoSgJ4aNCqwDqgAsiLiL', 'function': {'arguments': '{"a": 12, "b": 34}', 'name': 'plus_tool'}, 'type': 'function', 'index': 0}]}

tool_responsed的结果格式
meta=None content=[TextContent(type='text', text='46.0', annotations=None, meta=None)] structuredContent={'result': 46.0} isError=False

'''