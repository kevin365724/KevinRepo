from mcp.server.fastmcp import FastMCP
import aiofiles, asyncio

app = FastMCP("resource mcp", instructions="你是一个文件助手，可以帮助用户读取和写入文件内容")

@app.resource(
    uri="file://zhiliao.txt",
    name="zhiliao_file",
    description="获取知鸟课堂的相关信息",
    mime_type="text/plain"
)
async def zhiliao_resouce():
    async with aiofiles.open("zhiliao.txt", mode='r', encoding='utf-8') as f:
        content = await f.read()
    return content

# async def main():
#     result = await zhiliao_resouce()
#     print(result)

if __name__ == '__main__':
    app.run(transport="sse")
    # asyncio.run(main())