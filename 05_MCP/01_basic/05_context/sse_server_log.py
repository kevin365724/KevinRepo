#!/usr/bin/env python3
# -*- coding:utf-8 -*-
# sse_server.py
# @time:2025/9/15/23:04
from mcp.server.fastmcp import FastMCP, Context

app = FastMCP("sse_server_log")

@app.tool()
async def log_tool(files:list[str], cxt:Context):
    for index in range(len(files)):
        await cxt.info(f"Processing file {index + 1}/{len(files)}")
    return "All files processed."

if __name__ == '__main__':
    app.run(transport="sse")
