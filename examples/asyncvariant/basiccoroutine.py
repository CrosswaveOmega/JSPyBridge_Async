import asyncio
from javascriptasync import init_js, require_a, get_globalThis
init_js()
async def main():
  chalk, fs = await require_a("chalk"), await require_a("fs")
  globalThis=get_globalThis()
  datestr=await (await globalThis.Date(coroutine=True)).toLocaleString(coroutine=True)
  print("Hello", chalk.red("world!"), "it's", datestr)
  fs.writeFileSync("HelloWorld.txt", "hi!")

asyncio.run(main())