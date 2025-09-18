#!/usr/bin/env python3
# -*- coding:utf-8 -*-
# mcp_source.py
# @time:2025/9/9/23:32
# 1. 服务端代码
from mcp.server.fastmcp import FastMCP
import aiofiles


app = FastMCP("resource demo")


@app.resource(
    uri="file://zhiliao.txt",
    name="zhiliao",
    description="获取知了课堂的相关介绍信息",
    mime_type="text/plain"
)
async def zhiliao():
    """
    获取知了课堂的相关介绍信息
    """
    async with aiofiles.open("zhiliao.txt", mode="r", encoding='utf-8') as fp:
        content = await fp.read()
    return content


if __name__ == '__main__':
    app.run(transport="sse")