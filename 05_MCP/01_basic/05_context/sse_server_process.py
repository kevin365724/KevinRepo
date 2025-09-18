#!/usr/bin/env python3
# -*- coding:utf-8 -*-
# sse_server.py
# @time:2025/9/15/23:04
from mcp.server.fastmcp import FastMCP, Context
from mcp.types import RequestParams

app = FastMCP("sse_server_log")

@app.tool()
async def process_tool(files:list[str], cxt:Context):
    for index in range(len(files)):
        cxt.request_context.meta = RequestParams.Meta(progressToken= 1)
        # 有两个任务同时返回进度，第一个任务设置token为：1，第二个任务的token为：2.
        await cxt.report_progress(index + 1, len(files), f"Processing file {index + 1}/{len(files)}")

    return "All files processed."

if __name__ == '__main__':
    app.run(transport="sse")
