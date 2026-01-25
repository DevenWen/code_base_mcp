# Code Base MCP Server

A Model Context Protocol (MCP) server for code browsing, built with Python and uv.

# install
```bash
uv sync
```

# Usage
## init codebase
```bash
uv run code-base-cli \
  --code-path /home/Deven/workspace/lab/claude_agent_sdk_demo/.remote_java/wos-service \ 
  --include "com.vip.csc.wos.*" \
  --exclude "com.vip.csc.wos.util.*" \
  --report-id 5442474 \
  -v
```
输出：代码及覆盖率格式化数据库 dbs/wos-service.db  默认使用最后一个 wos-service 目录

## start mcp
```bash
export CODEBASE_REPORT_ID="5442474" # 设置报告ID
export CODEBASE_DB_PATH=dbs/wos-service.db # 设置数据库路径
uv run fastmcp run main.py:mcp --transport http --port 8000
claude mcp add --transport http code_base_mcp http://localhost:8000/mcp
claude 
```

## claude 
```bash
claude 
> "使用 SKILL 为 WoQueryOuterServiceImpl searchWorkOrderInfo 这个 Java 方法，生成全名 的测试用例"
```
