# Code Base MCP Server

`code-base-mcp` 是一个基于 [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) 的服务器，专为 Java 代码浏览、分析和测试用例生成而设计。它能够扫描 Java 代码库，提取其结构信息（类、方法、调用图），并将其存储在 SQLite 数据库中，供 LLM（如 Claude）调用。

## 主要功能

- **代码结构分析**：提取 Java 项目中的类、方法及其关系。
- **调用图生成**：支持生成 Mermaid 格式的方法调用图。
- **接口实现解析**：自动解析 Java 接口对应的实现类。
- **代码覆盖率集成**：支持集成外部代码覆盖率报告，分析未覆盖的代码路径。
- **参数 Schema 提取**：获取方法参数的 JSON Schema，辅助理解输入结构。
- **测试用例生成支持**：为 LLM 提供必要的上下文，辅助生成高质量的测试用例。

## 依赖环境和配置要求

- **Python**: 3.10 或更高版本。
- **uv**: 推荐使用 [uv](https://github.com/astral-sh/uv) 进行包管理和环境运行。
- **Java 代码库**: 需要分析的 Java 项目源代码。

## 安装步骤

1. **克隆仓库**:
   ```bash
   git clone <repository-url>
   cd code-base-mcp
   ```

2. **安装依赖**:
   使用 `uv` 同步环境：
   ```bash
   uv sync
   ```

## 快速上手

### 1. 初始化代码库数据库

在启动 MCP 服务器之前，需要先扫描 Java 项目并生成数据库文件。

```bash
uv run code-base-cli \
  --code-path /path/to/your/java/project \
  --repo-id my-project \
  --include "com.example.package.*" \
  --exclude "com.example.package.test.*" \
  --report-id COVERAGE_REPORT_ID \
  -v
```

- `--code-path`: Java 项目源代码根目录。
- `--repo-id`: (可选) 数据库标识，默认为目录名。生成的数据库将存放在 `dbs/` 目录下。
- `--include/--exclude`: (可选) 包含或排除的包路径模式。
- `--report-id`: (可选) 关联的覆盖率报告 ID。

### 2. 启动 MCP 服务器

设置必要的环境变量并运行服务器：

```bash
# 设置数据库路径（必须）
export CODEBASE_DB_PATH=dbs/my-project.db

# 设置覆盖率报告 ID（可选，如果初始化时提供了则推荐设置）
export CODEBASE_REPORT_ID="COVERAGE_REPORT_ID"

# 启动服务器（默认使用 HTTP 传输）
uv run fastmcp run main.py:mcp --transport http --port 8000
```

### 3. 在 Claude 中配置

你可以将此服务器添加到 Claude Desktop 或 CLI 中：

**Claude CLI:**
```bash
claude mcp add code_base_mcp http://localhost:8000/mcp --transport http
```

## 可用工具 (MCP Tools)

服务器注册了以下工具供 LLM 使用：

- `resolve_interface_to_impl_tool`: 解析 Java 接口到其具体实现类。
- `get_call_graph_tool`: 获取指定方法的调用图（Mermaid 格式）。
- `get_method_json_schema_tool`: 获取方法参数的 JSON Schema。
- `get_method_with_coverage_tool`: 获取方法源码及其代码覆盖率统计。
- `get_callers_tool`: 查询调用指定方法的所有上游方法。
- `get_callees_tool`: 查询指定方法调用的所有下游方法。
- `save_test_cases_tool`: 将生成的测试用例保存到本地 `log/` 目录。

## 常见问题及解决办法

### 1. 数据库未找到
**现象**: 工具返回 "Error: Database path not configured."
**解决**: 确保在启动 MCP 服务器前正确设置了 `CODEBASE_DB_PATH` 环境变量。

### 2. 覆盖率数据缺失
**现象**: `get_method_with_coverage_tool` 返回没有覆盖率信息。
**解决**:
- 确保在初始化数据库时使用了 `--report-id`。
- 确保启动服务器时设置了 `CODEBASE_REPORT_ID` 环境变量。
- 检查 `java_call_graph/coverage.py` 中的报告获取逻辑是否匹配你的报告格式。

### 3. 解析 Java 代码失败
**现象**: 扫描过程中出现解析错误。
**解决**: `javalang` 可能不支持最新的 Java 语法特性。尝试排除某些复杂的包或检查代码是否符合标准 Java 规范。

## 开发

项目结构：
- `java_call_graph/`: 核心逻辑，包括扫描、解析、存储和查询。
- `tools/`: MCP 工具定义。
- `cli.py`: 数据库初始化命令行工具。
- `main.py`: MCP 服务器入口。

如果你需要添加新的工具，请在 `tools/code_base_tools.py` 中的 `register_code_base_tools` 函数内进行注册。
