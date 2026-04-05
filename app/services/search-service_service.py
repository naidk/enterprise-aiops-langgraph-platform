import asyncio
from asyncio import TimeoutError

async def search_query(query):
    try:
        # Assuming this is the function causing the latency
        # Implement a timeout of 25 seconds to allow for some buffer time
        async with asyncio.timeout(25):
            # Simulating the search query
            await asyncio.sleep(1)  # Replace with actual query execution
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