#!/usr/bin/env python3
# -*- coding:utf-8 -*-
# sse_server.py
# @time:2025/9/15/23:04
from mcp.server.fastmcp import FastMCP, Context
from mcp.types import SamplingMessage, TextContent

app = FastMCP("sse_server_log")

@app.tool()
async def sampling_tool(ctx: Context):
    # 直接发送一个Sampling的消息
    response = await ctx.session.create_message(
        messages=[SamplingMessage(role="user", content=TextContent(type="text", text="请帮我按照主题“知了课堂上新了MCP课程”为主题写两篇新闻。"))],
        max_tokens=2048
    )
    print(response)
    return "采样成功"

if __name__ == '__main__':
    app.run(transport="sse")
