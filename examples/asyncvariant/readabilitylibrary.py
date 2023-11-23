# Import the required libraries/modules
import asyncio
import re
from javascriptasync import init_js_a, require_a, eval_js_a


# Define an asynchronous function to read an article
async def read_article_async(url):
    # Initialize the Javascript async runtime
    await init_js_a()

    # Import the @mozilla/readability library from Javascript
    readability = await require_a("@mozilla/readability")

    # Import the read_webpage_plain function from a local Javascript file
    read_webpage_plain = (await require_a("./readwebpage.js")).read_webpage_plain

    # Import the jsdom library from Javascript
    jsdom = await require_a("jsdom")

    # Create a python object with variable as the provided URL
    pythonObject = {"var": url}

    # Define a Javascript code snippet
    out = """
    let urla=await pythonObject.var
    let result=await read_webpage_plain(urla,readability,jsdom);
    return [result[0],result[1]];
    """

    # Run the Javascript code snippet and catch the result, waits at most 30 seconds for the result
    rsult = await eval_js_a(out, timeout=30)

    # Deconstruct the result into output and header
    output, header = rsult[0], rsult[1]

    # Turn the header into a python dictionary
    await header.get_dict_a()

    # Cleaning the output text
    simplified_text = output.strip()  # Removes leading/trailing white spaces

    # Print the cleaned text
    print(simplified_text)

    # Return a list of the cleaned text and the article's title
    return [simplified_text, header.get('title')]


# URL of the article to be read
URL="https://en.wikipedia.org/wiki/Python_(programming_language)"

# Running the async function to read the article from the given url
asyncio.run(read_article_async(URL))