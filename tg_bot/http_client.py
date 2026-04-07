import httpx

http = httpx.AsyncClient(timeout=httpx.Timeout(30.0))
