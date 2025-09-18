#!/usr/bin/env python3
# -*- coding:utf-8 -*-
# mcp_stdio.py
# @time:2025/9/9/22:46
from mcp.server.fastmcp import FastMCP

app = FastMCP("start mcp")

@app.tool()
def plus_tool(a: float, b: float) -> float:
    """
    计算两数相加的结果
    :param a: 相加的第一个数
    :param b: 相加的第二个数
    :return: 返回两数相加的结果
    """
    return a + b


if __name__ == '__main__':
    app.run(transport='stdio')