#!/usr/bin/env python3
# -*- coding:utf-8 -*-
# stdio_server.py
# @time:2025/9/14/21:38
from mcp.server.fastmcp import FastMCP

app=FastMCP("start mcp", instructions="你是一个计算器，可以进行加减乘除运算")

@app.tool()
def plus_tool(a: float,b: float) -> float:
    """
    计算两数相加的工具
    :param a: 第一个相加的数
    :param b: 第二个相加的数
    :return: 返回两数相加后的结果
    """
    return a + b

@app.tool()
def minus_tool(a: float,b: float) -> float:
    """
    计算两数相减的工具
    :param a: 被减数
    :param b: 减数
    :return: 返回两数相减后的结果
    """
    return a - b

if __name__ == '__main__':
    app.run(transport="stdio")