import asyncio

import re

from javascriptasync import init_js, require_a, eval_js_a,get_globalThis
init_js()
async def read_article_async():
    url='https://en.wikipedia.org/wiki/F-Zero'

    readability= await require_a('@mozilla/readability')
    read_webpage_plain=(await require_a('./readwebpage.js')).read_webpage_plain
    jsdom=await require_a('jsdom')
    TurndownService=await require_a('turndown')

    pythonObject = {"var": url}
    out='''
    let urla=await pythonObject.var
    
    const turndownService = new TurndownService({ headingStyle: 'atx' });
    let result=await read_webpage_plain(urla,readability,jsdom,turndownService);
    return [result[0],result[1]];
    '''

    print(out)
    
    rsult= await eval_js_a(out,timeout=30)

    output,header=rsult[0],rsult[1]
    simplified_text = output.strip()
    simplified_text = re.sub(r'(\n){4,}', '\n\n\n', simplified_text)
    simplified_text = re.sub(r'\n\n', ' ', simplified_text)
    simplified_text = re.sub(r' {3,}', '  ', simplified_text)
    simplified_text = simplified_text.replace('\t', '')
    simplified_text = re.sub(r'\n+(\s*\n)*', '\n', simplified_text)
    print(simplified_text)
    return [simplified_text, header]

asyncio.run(read_article_async())