<p align="center">
  <img src="https://inject3r.github.io/atomhttp/logo.jpg" alt="AtomHTTP Logo" width="350">
</p>

# AtomHTTP

A modern, developer-friendly HTTP client for Python with a familiar API, powerful request handling, optional asynchronous support, and built-in tools for concurrent requests, uploads, downloads, retries, cookies, interceptors, streaming, and testing.

Designed to feel simple for everyday requests while providing the flexibility required for production applications.

## Features

* **Simple, familiar API** — Make HTTP requests with a clean interface inspired by popular HTTP clients.
* **Synchronous by default** — Use AtomHTTP without configuring an event loop or asynchronous environment.
* **Optional asynchronous API** — Use `async`/`await` when asynchronous workflows are required.
* **Concurrent requests** — Execute multiple requests concurrently with a simple batch API.
* **Request & response interceptors** — Modify requests and responses globally or per client.
* **Upload & download progress** — Monitor transfer progress through incremental callbacks.
* **Multipart & form submissions** — Easily send form data and file uploads.
* **Cookie management** — Persistent cookie handling with automatic cookie propagation between requests.
* **XSRF protection** — Automatic XSRF header support for applications that require it.
* **Multiple response formats** — Work with JSON, text, binary data, or streaming responses.
* **Configurable retries** — Automatically retry failed requests with configurable backoff behavior.
* **Redirect handling** — Follow HTTP redirects with configurable behavior.
* **Proxy support** — Route requests through HTTP and other supported proxy configurations.
* **Connection pooling** — Efficiently reuse network connections across requests.
* **Unix domain sockets** — Communicate with services exposed through Unix sockets.
* **Mock adapter** — Test HTTP-based applications without performing real network requests.
* **Fully typed** — Includes type information for modern Python development environments.

## Installation

```bash
pip install atomhttp
```

For development and testing:

```bash
pip install "atomhttp[test]"
```

## Quick Start

### Basic Request

```python
from atomhttp import AtomHTTP

client = AtomHTTP(base_url="https://api.example.com")

response = client.get("/users/1")

print(response.status)
print(response.data)
```

### One-Off Requests

For simple requests, a client instance is not required:

```python
import atomhttp

response = atomhttp.get("https://api.example.com/users/1")

print(response.data)
```

## HTTP Methods

AtomHTTP provides a consistent interface for common HTTP methods:

```python
response = client.get("/users")

response = client.post("/users", data={
    "name": "Ada"
})

response = client.put("/users/1", data={
    "name": "Ada Lovelace"
})

response = client.patch("/users/1", data={
    "name": "Ada"
})

response = client.delete("/users/1")
```

## Request Configuration

Requests can be configured with headers, query parameters, request data, and other options:

```python
response = client.get(
    "/users",
    params={
        "page": 1,
        "limit": 20,
    },
    headers={
        "Authorization": "Bearer <token>",
    },
)
```

## JSON Requests

Send JSON payloads directly:

```python
response = client.post(
    "/users",
    json={
        "name": "Ada Lovelace",
        "email": "ada@example.com",
    },
)
```

The response can then be accessed through the unified response interface:

```python
print(response.status)
print(response.data)
```

## Asynchronous API

Asynchronous support is available when needed:

```python
import asyncio

from atomhttp import AsyncAtomHTTP


async def main():
    async with AsyncAtomHTTP(
        base_url="https://api.example.com"
    ) as client:

        response = await client.get("/users/1")

        print(response.data)


asyncio.run(main())
```

The asynchronous API follows the same overall interface, making it easy to switch between synchronous and asynchronous applications.

## Concurrent Requests

Run multiple requests concurrently with a single call.

### Synchronous

```python
responses = client.all([
    lambda: client.get("/users/1"),
    lambda: client.get("/users/2"),
    lambda: client.get("/users/3"),
])

for response in responses:
    print(response.data)
```

### Asynchronous

```python
responses = await async_client.all([
    async_client.get("/users/1"),
    async_client.get("/users/2"),
    async_client.get("/users/3"),
])

for response in responses:
    print(response.data)
```

## File Uploads

Uploading files is straightforward:

```python
from atomhttp import FormData

form = FormData()

form.append("username", "ada")
form.append(
    "avatar",
    open("photo.jpg", "rb"),
    filename="photo.jpg",
)

response = client.post(
    "/profile",
    data=form,
)
```

## Upload & Download Progress

Track transfer progress using callbacks:

```python
def on_progress(current, total):
    if total:
        percentage = (current / total) * 100
        print(f"{percentage:.1f}%")


response = client.get(
    "/large-file.zip",
    on_download_progress=on_progress,
)
```

Progress callbacks are invoked incrementally during the transfer, making them suitable for CLI applications, desktop applications, and other interfaces that need real-time progress reporting.

## Interceptors

Intercept requests before they are sent:

```python
def add_auth(config):
    config.headers["Authorization"] = f"Bearer {get_token()}"
    return config


client.interceptors.request.use(add_auth)
```

Response interceptors can be used for centralized response processing:

```python
def handle_response(response):
    return response


client.interceptors.response.use(handle_response)
```

Interceptors are useful for authentication, logging, request transformation, error handling, and application-wide policies.

## Cookies

Cookie handling is built into the client:

```python
client = AtomHTTP(
    base_url="https://example.com"
)

client.get("/login")

response = client.get("/dashboard")
```

Cookies received from the server can automatically be reused by subsequent requests made through the same client.

## Retries

Configure automatic retries for transient failures:

```python
client = AtomHTTP(
    base_url="https://api.example.com",
    retry_config={
        "total": 3,
        "backoff_factor": 0.5,
    },
)
```

Retry behavior can be adjusted according to the requirements of your application.

## Streaming Responses

Large responses can be consumed as a stream instead of loading the entire payload into memory:

```python
response = client.get(
    "/large-file.zip",
    response_type="stream",
)

for chunk in response.iter_bytes():
    process(chunk)
```

This is useful for large downloads, media files, data processing pipelines, and other memory-sensitive workloads.

## Unix Domain Sockets

AtomHTTP can communicate with services exposed through Unix domain sockets:

```python
client = AtomHTTP(
    base_url="http+unix://%2Fvar%2Frun%2Fdocker.sock"
)

response = client.get("/version")

print(response.data)
```

## Mocking & Testing

Use the mock adapter to test HTTP interactions without making real network requests:

```python
from atomhttp import AtomHTTP, MockAdapter

mock = MockAdapter()

mock.on(
    "GET",
    "/users/1",
    status=200,
    data={
        "id": 1,
        "name": "Ada",
    },
)

client = AtomHTTP(adapter=mock)

response = client.get("/users/1")

assert response.status == 200
assert response.data["name"] == "Ada"
```

This makes it possible to test API integrations deterministically and independently from external services.

## Response Handling

Responses expose a consistent interface:

```python
response.status
response.headers
response.data
response.text
```

Depending on the configured response type, binary and streaming data can also be accessed through the response object.

## Client Configuration

A reusable client can be configured once and shared throughout an application:

```python
client = AtomHTTP(
    base_url="https://api.example.com",
    headers={
        "Accept": "application/json",
    },
)
```

This is particularly useful when working with APIs that share authentication, headers, retry policies, or other common configuration.

## Error Handling

HTTP and transport errors can be handled explicitly:

```python
try:
    response = client.get("/users/1")
except Exception as exc:
    print(f"Request failed: {exc}")
```

For production applications, errors can be handled centrally through interceptors or application-specific exception handling.

## Requirements

* Python 3.8+

## Testing

Install the development dependencies:

```bash
pip install -e ".[test]"
```

Run the test suite:

```bash
pytest
```

## Type Checking

AtomHTTP includes type information and is designed to work with modern Python type-checking and IDE tooling.

## License

See the `LICENSE` file for licensing information.

## Contributing

Contributions are welcome.

Before submitting a pull request:

1. Add or update tests for your changes.
2. Ensure the test suite passes.
3. Keep public APIs backward-compatible whenever possible.
4. Keep changes focused and well documented.

## Documentation

For complete API documentation, examples, configuration options, and advanced usage, visit the project documentation.

---

**AtomHTTP** — a clean, powerful HTTP client for Python.
