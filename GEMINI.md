# GEMINI.md - code-base-mcp

This file provides instructional context for the `code-base-mcp` project, an MCP server designed for Java code browsing and analysis.

## Project Overview
`code-base-mcp` is a Model Context Protocol (MCP) server that enables LLMs to explore and analyze Java source code. It scans a Java repository, extracts its structural information (classes, methods, call graphs), and stores it in a SQLite database. It also supports integrating code coverage data from external reports.

### Main Technologies
- **Python 3.10+**: Core implementation language.
- **uv**: Package and environment management.
- **FastMCP**: Framework for building the MCP server.
- **javalang**: For parsing Java source code.
- **SQLite**: For storing scanned code metadata and coverage.
- **BeautifulSoup4 & Requests**: For fetching and parsing coverage reports.

### Architecture
- `java_call_graph/`: Contains the core logic for scanning (`scanner.py`), parsing (`parser.py`), storing (`storage.py`), and querying (`query.py`) Java codebases.
- `tools/`: Defines the MCP tools exposed to the LLM.
- `cli.py`: A command-line tool to initialize the codebase database.
- `main.py`: The entry point for the MCP server.
- `dbs/`: Directory where generated SQLite databases are stored.
- `log/`: Directory for saved test cases and logs.

## Building and Running

### Installation
Ensure you have `uv` installed, then run:
```bash
uv sync
```

### Initializing the Codebase
Before starting the MCP server, you must scan a Java codebase to create a database:
```bash
uv run code-base-cli --code-path /path/to/your/java/project --repo-id my-project [--report-id COVERAGE_ID]
```
- `--code-path`: Path to the Java source directory.
- `--repo-id`: (Optional) ID for the database file (default: directory name).
- `--report-id`: (Optional) ID for a coverage report.
- `--include/--exclude`: (Optional) Package patterns to include or exclude.

### Starting the MCP Server
To start the MCP server, provide the database path and optional report ID via environment variables:
```bash
export CODEBASE_DB_PATH=dbs/my-project.db
export CODEBASE_REPORT_ID="COVERAGE_ID" # Optional
uv run fastmcp run main.py:mcp --transport http --port 8000
```

## Development Conventions

### Coding Style
- Follow standard Python (PEP 8) conventions.
- Use type hints for better code clarity and maintainability.
- Keep MCP tool definitions in `tools/code_base_tools.py`.

### Tool Definitions
New MCP tools should be registered within `register_code_base_tools(mcp)` in `tools/code_base_tools.py`. Tools should generally:
- Validate that `_DB_PATH` is set.
- Use functions from `java_call_graph.query` to interact with the database.
- Return results as strings (often JSON-formatted).

### Data Storage
- Schema for the database is defined in `java_call_graph/schema.sql`.
- `java_call_graph/storage.py` handles all SQLite interactions.
- `java_call_graph/models.py` contains the data models for classes, methods, and calls.
