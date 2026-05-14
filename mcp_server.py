import argparse
import json
import os
from fastmcp import FastMCP
from db import create_adapter, ValidationError, MAX_ROWS
from init_db import create_database

create_database()

mcp = FastMCP("SQLite Lab MCP Server")
adapter = create_adapter()


@mcp.tool(name="search")
def search(
    table: str,
    columns: list[str] | None = None,
    filters: list[dict] | None = None,
    limit: int = 20,
    offset: int = 0,
    order_by: str | None = None,
    descending: bool = False,
) -> str:
    """
    Search rows in a database table.

    filters format: [{"column": "cohort", "op": "=", "value": "A1"}]
    Supported ops: =, !=, >, >=, <, <=, LIKE
    Max rows returned: 100. Use offset for pagination. Response includes has_more flag.
    """
    try:
        result = adapter.search(table, columns, filters, min(limit, MAX_ROWS), offset, order_by, descending)
        return json.dumps(result, ensure_ascii=False)
    except ValidationError as e:
        return json.dumps({"error": str(e)})


@mcp.tool(name="insert")
def insert(table: str, values: dict) -> str:
    """
    Insert a new row into a database table.

    values format: {"name": "Nguyen Van X", "cohort": "A1", "score": 8.0}
    Returns the inserted payload including the generated id.
    """
    try:
        result = adapter.insert(table, values)
        return json.dumps(result, ensure_ascii=False)
    except ValidationError as e:
        return json.dumps({"error": str(e)})


@mcp.tool(name="aggregate")
def aggregate(
    table: str,
    metric: str,
    column: str | None = None,
    filters: list[dict] | None = None,
    group_by: str | None = None,
) -> str:
    """
    Run an aggregate query on a table.

    metric: COUNT, AVG, SUM, MIN, MAX
    column: required for AVG/SUM/MIN/MAX; optional for COUNT (defaults to *)
    group_by: optional column name to group results by
    filters format: [{"column": "cohort", "op": "=", "value": "A1"}]
    """
    try:
        rows = adapter.aggregate(table, metric, column, filters, group_by)
        return json.dumps({"rows": rows, "metric": metric.upper()}, ensure_ascii=False)
    except ValidationError as e:
        return json.dumps({"error": str(e)})


@mcp.resource("schema://database")
def database_schema() -> str:
    """Return the full database schema as JSON."""
    tables = adapter.list_tables()
    schema = {t: adapter.get_table_schema(t) for t in tables}
    return json.dumps(schema, ensure_ascii=False, indent=2)


@mcp.resource("schema://table/{table_name}")
def table_schema(table_name: str) -> str:
    """Return the schema for a single table as JSON."""
    try:
        schema = adapter.get_table_schema(table_name)
        return json.dumps({"table": table_name, "columns": schema}, ensure_ascii=False, indent=2)
    except ValidationError as e:
        return json.dumps({"error": str(e)})


# ------------------------------------------------------------------ #
#  HTTP / SSE transport with Bearer token auth (bonus)                #
# ------------------------------------------------------------------ #

def _build_http_app(transport: str):
    """Return a Starlette ASGI app for HTTP/SSE transport."""
    try:
        http_app = mcp.http_app(transport=transport)
    except TypeError:
        http_app = mcp.http_app()

    api_key = os.getenv("MCP_API_KEY", "")
    if api_key:
        from starlette.middleware.base import BaseHTTPMiddleware
        from starlette.responses import JSONResponse

        class _BearerAuth(BaseHTTPMiddleware):
            async def dispatch(self, request, call_next):
                auth = request.headers.get("Authorization", "")
                xkey = request.headers.get("X-API-Key", "")
                if auth == f"Bearer {api_key}" or xkey == api_key:
                    return await call_next(request)
                return JSONResponse({"error": "Unauthorized"}, status_code=401)

        http_app.add_middleware(_BearerAuth)
        print(f"Auth enabled — set header:  Authorization: Bearer {api_key}")

    return http_app


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SQLite Lab MCP Server")
    parser.add_argument("--transport", default="stdio", choices=["stdio", "http", "sse"],
                        help="Transport type (default: stdio)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    if args.transport in ("http", "sse"):
        try:
            import uvicorn
            transport_name = "streamable-http" if args.transport == "http" else "sse"
            http_app = _build_http_app(transport_name)
            print(f"MCP server → http://{args.host}:{args.port}/mcp")
            uvicorn.run(http_app, host=args.host, port=args.port)
        except ImportError:
            print("uvicorn not installed. Run: pip install uvicorn")
        except AttributeError:
            print("FastMCP http_app() not available in this version — falling back to stdio")
            mcp.run()
    else:
        mcp.run()
