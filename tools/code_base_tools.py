"""
Code Base Tools for FastMCP

从 llm_testcase_asker2.py 提取的 MCP 工具，使用 FastMCP 格式注册。
支持 Java 代码分析和测试用例生成。
"""

import json
import os
from datetime import datetime
from typing import Optional

from java_call_graph.query import (
    get_call_graph,
    get_method_json_schema,
    get_callers,
    get_callees,
    get_method_by_name_with_coverage,
    resolve_interface_to_impl,
)
from java_call_graph.storage import CallGraphDB
from java_call_graph.adapter import to_mermaid


# ==================== 全局配置 ====================

# 从环境变量读取配置
# CODEBASE_DB_PATH: 数据库文件路径
# CODEBASE_REPORT_ID: 覆盖率报告 ID（可选）
# CODEBASE_LOG_DIR: 日志目录（可选，默认为 "log"）
_DB_PATH: str = os.environ.get("CODEBASE_DB_PATH", "")
_REPORT_ID: Optional[str] = os.environ.get("CODEBASE_REPORT_ID")
_LOG_DIR: str = os.environ.get("CODEBASE_LOG_DIR", "log")


def set_db_path(db_path: str, report_id: Optional[str] = None):
    """设置数据库路径和报告ID"""
    global _DB_PATH, _REPORT_ID
    _DB_PATH = db_path
    _REPORT_ID = report_id


def get_db_path() -> str:
    """获取当前数据库路径"""
    return _DB_PATH


def get_report_id() -> Optional[str]:
    """获取当前报告ID"""
    return _REPORT_ID


# ==================== 注册工具到 FastMCP ====================


def register_code_base_tools(mcp):
    """
    将所有代码分析工具注册到 FastMCP 实例。

    Args:
        mcp: FastMCP 实例
    """

    @mcp.tool()
    def resolve_interface_to_impl_tool(interface_name: str) -> str:
        """
        解析 Java 接口到其实现类。
        如果只有一个实现类，返回该实现类名；否则返回原接口名。

        Args:
            interface_name: 接口名称

        Returns:
            实现类名或原接口名
        """
        if not _DB_PATH:
            return "Error: Database path not configured. Call set_db_path first."

        db = CallGraphDB(_DB_PATH)
        result = resolve_interface_to_impl(interface_name, db)
        return result

    @mcp.tool()
    def get_call_graph_tool(method_name: str, depth: int = 2) -> str:
        """
        获取指定方法的调用图，返回 Mermaid 格式的流程图。
        用于分析方法的调用链。

        Args:
            method_name: 方法名称（格式：ClassName.methodName）
            depth: 调用深度，默认为 2

        Returns:
            Mermaid 格式的调用图
        """
        if not _DB_PATH:
            return "Error: Database path not configured. Call set_db_path first."

        graph = get_call_graph(
            _DB_PATH, method_name, depth=depth, only_known_methods=True
        )
        mermaid_str = to_mermaid(graph)
        return mermaid_str

    @mcp.tool()
    def get_method_json_schema_tool(method_name: str) -> str:
        """
        获取方法参数的 JSON Schema，用于了解方法的输入参数结构。

        Args:
            method_name: 方法名称（格式：ClassName.methodName）

        Returns:
            JSON Schema 字符串
        """
        if not _DB_PATH:
            return "Error: Database path not configured. Call set_db_path first."

        schema = get_method_json_schema(_DB_PATH, method_name)
        return json.dumps(schema, ensure_ascii=False, indent=2)

    @mcp.tool()
    def get_method_with_coverage_tool(method_name: str) -> str:
        """
        获取方法的代码覆盖率信息，包括已覆盖、部分覆盖、未覆盖的行数统计。

        Args:
            method_name: 方法名称（格式：ClassName.methodName）

        Returns:
            包含方法信息和覆盖率的 JSON 字符串
        """
        if not _DB_PATH:
            return "Error: Database path not configured. Call set_db_path first."

        if not _REPORT_ID:
            return "No coverage report ID configured."

        method_info, coverage = get_method_by_name_with_coverage(
            _DB_PATH, method_name, _REPORT_ID
        )

        if not method_info:
            return f"Method not found: {method_name}"

        result = {
            "method_name": method_info.get("full_name"),
            "source_code": method_info.get("source_code"),
        }

        if coverage:
            result["coverage"] = {
                "total_lines": coverage.total_lines,
                "covered_lines": coverage.covered_lines,
                "partial_lines": coverage.partial_lines,
                "uncovered_lines": coverage.uncovered_lines,
                "coverage_rate": coverage.coverage_rate,
            }

        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    def get_callers_tool(method_name: str, depth: int = 1) -> str:
        """
        查询谁调用了指定的方法，返回调用者方法名列表。

        Args:
            method_name: 方法名称（格式：ClassName.methodName）
            depth: 向上追溯的层数，默认为 1

        Returns:
            调用者列表的 JSON 字符串
        """
        if not _DB_PATH:
            return "Error: Database path not configured. Call set_db_path first."

        callers = get_callers(_DB_PATH, method_name, depth=depth)
        return json.dumps(callers, ensure_ascii=False, indent=2)

    @mcp.tool()
    def get_callees_tool(method_name: str, depth: int = 1) -> str:
        """
        查询指定方法调用了哪些其他方法，返回被调用方法名列表。

        Args:
            method_name: 方法名称（格式：ClassName.methodName）
            depth: 向下追溯的层数，默认为 1

        Returns:
            被调用者列表的 JSON 字符串
        """
        if not _DB_PATH:
            return "Error: Database path not configured. Call set_db_path first."

        callees = get_callees(_DB_PATH, method_name, depth=depth)
        return json.dumps(callees, ensure_ascii=False, indent=2)

    @mcp.tool()
    def save_test_cases_tool(test_cases: list) -> str:
        """
        保存测试用例到 log 目录。文件名格式：yyyyMMddHHMMSS_test_case.json

        Args:
            test_cases: 测试用例列表

        Returns:
            保存结果消息
        """
        # 确保 log 目录存在
        os.makedirs(_LOG_DIR, exist_ok=True)

        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"{timestamp}_test_case.json"
        filepath = os.path.join(_LOG_DIR, filename)

        # 保存文件
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(test_cases, f, ensure_ascii=False, indent=2)

        return f"Test cases saved to: {filepath}"
