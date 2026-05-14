# SQLite MCP Server — Setup & Demo Guide

## Project Structure

```
.
├── init_db.py       # Creates school.db with schema and seed data
├── db.py            # SQLiteAdapter — all SQL logic with validation
├── mcp_server.py    # FastMCP server — tools and resources
├── requirements.txt
├── .mcp.json        # Claude Code client config
├── school.db        # Generated SQLite database (after running init_db.py)
└── pseudocode/      # Original pseudocode skeletons (reference only)
```

---

## Setup Instructions

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Initialize the database

```bash
python init_db.py
```

Creates `school.db` with three tables and seed data:
- `students` — 10 rows across cohorts A1, A2, B1, B2
- `courses` — 5 courses
- `enrollments` — 18 enrollment records

### 3. Start the MCP server

```bash
python mcp_server.py
```

The server runs over stdio and is ready for MCP client connections.

---

## Testing Steps

### Option A — MCP Inspector (recommended)

```bash
npx @modelcontextprotocol/inspector python mcp_server.py
```

Open the URL printed in the terminal and verify:

| Check | Expected result |
|-------|----------------|
| Tools tab → List Tools | `search`, `insert`, `aggregate` with descriptions |
| Resources tab → List Resources | `database_schema` (`schema://database`) |
| Resources tab → List Templates | `table_schema` (`schema://table/{table_name}`) |
| Run `search` on `students`, filter cohort=A1 | Returns 3 student rows |
| Run `insert` on `students` with valid values | `{"inserted": true, "id": ..., "data": {...}}` |
| Run `aggregate` AVG on `score` group by `cohort` | Avg score per cohort |
| Run `search` on table `hackers` | `{"error": "Unknown table: 'hackers'"}` |

### Option B — Quick Python smoke test

```bash
python -c "
from db import SQLiteAdapter
db = SQLiteAdapter()
print('Tables:', db.list_tables())
print('Search A1:', db.search('students', filters=[{'column':'cohort','op':'=','value':'A1'}]))
print('Avg score:', db.aggregate('students', 'AVG', 'score', group_by='cohort'))
print('Insert:', db.insert('students', {'name':'Test','cohort':'A1','score':9.0}))
"
```

---

## Tool Reference

### `search`

```json
{
  "table": "students",
  "filters": [{"column": "cohort", "op": "=", "value": "A1"}],
  "order_by": "score",
  "descending": true,
  "limit": 10,
  "offset": 0
}
```

Supported operators: `=`, `!=`, `>`, `>=`, `<`, `<=`, `LIKE`

### `insert`

```json
{
  "table": "students",
  "values": {"name": "Nguyen Van X", "cohort": "A1", "score": 8.0, "email": "x@example.com"}
}
```

### `aggregate`

```json
{
  "table": "students",
  "metric": "AVG",
  "column": "score",
  "group_by": "cohort"
}
```

Supported metrics: `COUNT`, `AVG`, `SUM`, `MIN`, `MAX`

---

## MCP Resources

| URI | Description |
|-----|-------------|
| `schema://database` | Full schema of all tables as JSON |
| `schema://table/{table_name}` | Schema for a single table (e.g. `schema://table/students`) |

---

## Claude Code Client Configuration

The `.mcp.json` at the project root configures Claude Code to use this server:

```json
{
  "mcpServers": {
    "sqlite-lab": {
      "type": "stdio",
      "command": "python",
      "args": ["C:\\Users\\ACER\\Downloads\\Day26-Track3-HoTranDinhNguyen-2A202600080\\mcp_server.py"]
    }
  }
}
```

Verify in Claude Code by referencing `@sqlite-lab:schema://database`.

---

## Demo Scenarios

1. **Search students in cohort A1** — `search` with filter `cohort = A1`
2. **Insert a new student** — `insert` into `students`
3. **Count rows per cohort** — `aggregate` COUNT, group by `cohort`
4. **Average score by cohort** — `aggregate` AVG on `score`, group by `cohort`
5. **Read full schema** — resource `schema://database`
6. **Read per-table schema** — resource `schema://table/students`
7. **Invalid request** — `search` on non-existent table → clear error message
