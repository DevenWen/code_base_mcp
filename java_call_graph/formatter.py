"""
代码格式化工具 - 带覆盖率标记

将源代码与覆盖率数据合并，生成带左侧标记的代码文本。
"""

from typing import List, Dict
from java_call_graph.models import CoverageLine, CoverageState


# 覆盖状态到标记的映射
COVERAGE_MARKERS = {
    CoverageState.FULL: "[fc]",
    CoverageState.PARTIAL: "[pc]",
    CoverageState.NONE: "[nc]",
}


def format_code_with_coverage(
    source_code: str,
    start_line: int,
    coverage_lines: List[CoverageLine],
) -> str:
    """
    将方法源代码与覆盖率数据合并，生成带左侧标记的代码文本

    Args:
        source_code: 方法源代码
        start_line: 方法起始行号（1-indexed）
        coverage_lines: 覆盖率数据列表

    Returns:
        格式化后的代码字符串，每行左侧带覆盖率标记
    """
    if not source_code:
        return ""

    # 构建行号到覆盖状态的映射
    coverage_map: Dict[int, CoverageState] = {}
    for line in coverage_lines:
        coverage_map[line.line_number] = line.coverage_state

    # 分割源代码为行
    lines = source_code.split("\n")
    formatted_lines = []

    for i, line_content in enumerate(lines):
        line_number = start_line + i
        coverage_state = coverage_map.get(line_number)

        if coverage_state:
            marker = COVERAGE_MARKERS.get(coverage_state, "")
            formatted_lines.append(f"{marker} | {line_content}")
        else:
            # 无覆盖数据时不显示标记，保持对齐
            formatted_lines.append(f"     | {line_content}")

    return "\n".join(formatted_lines)


def get_coverage_legend() -> str:
    """
    返回覆盖率标记的说明文本

    Returns:
        说明文本
    """
    return """以下代码中，每行左侧标注了当前测试的覆盖状态：
- [fc] = 该行已被测试完全覆盖
- [pc] = 该行被部分覆盖（如条件语句只测试了部分分支）
- [nc] = 该行未被任何测试覆盖
- 无标记 = 该行无覆盖数据（可能是注释或空行）"""


def format_coverage_summary(
    total_lines: int,
    covered_lines: int,
    partial_lines: int,
    uncovered_lines: int,
    coverage_rate: float,
) -> str:
    """
    格式化覆盖率统计信息

    Args:
        total_lines: 总行数
        covered_lines: 已覆盖行数
        partial_lines: 部分覆盖行数
        uncovered_lines: 未覆盖行数
        coverage_rate: 覆盖率（0-1）

    Returns:
        格式化的统计文本
    """
    return f"""## 当前覆盖率统计
- 总行数: {total_lines}
- 已覆盖: {covered_lines} ({covered_lines / total_lines * 100:.1f}%)
- 部分覆盖: {partial_lines} ({partial_lines / total_lines * 100:.1f}%)
- 未覆盖: {uncovered_lines} ({uncovered_lines / total_lines * 100:.1f}%)
- 覆盖率: {coverage_rate * 100:.1f}%"""
