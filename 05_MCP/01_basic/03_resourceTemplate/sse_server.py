from mcp.server.fastmcp import FastMCP
import aiofiles, json, asyncio

app = FastMCP("resource template mcp")


@app.resource(
    uri="file://data/{grade}.json",
    name="grade_score",
    description="这边提供了一个成绩查询的MCP resource，可以根据年级grade，查询详情年级成绩信息。\n:param grade: 年级，根据用户提供的信息，转换成如下信息中的一个：grade_1、grade_2、grade_3",
    mime_type="application/json"
)
async def score_detail(grade: str):
    async with aiofiles.open(f"data/{grade}.json", mode='r', encoding='utf-8') as f:
        content = json.loads(await f.read())
    return content


if __name__ == '__main__':
    app.run(transport="sse")
