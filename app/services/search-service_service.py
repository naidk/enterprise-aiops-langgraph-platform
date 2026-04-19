import asyncio
from asyncio import TimeoutError

async def search_query(query):
    try:
        # Assuming this is the function that's taking too long
        # Add a timeout to this function
        async with asyncio.timeout(25):  # 25 seconds timeout to account for other overheads
            # Simulating the search query
            await asyncio.sleep(1)  # Replace with actual search query
            return ["result1", "result2"]
    except TimeoutError:
        # Handle the timeout error
        return ["Error: Timeout occurred"]

async def handle_search_request(query):
    results = await search_query(query)
    return results

# Example usage
async def main():
    query = "example query"
    results = await handle_search_request(query)
    print(results)

asyncio.run(main())