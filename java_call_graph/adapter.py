"""Adapter module for converting CallGraph to different formats."""

from java_call_graph.models import CallGraph


def to_mermaid(graph: CallGraph, direction: str = "TD") -> str:
    """
    将 CallGraph 转换为 Mermaid 图格式

    Args:
        graph: CallGraph 实例
        direction: 图方向，TD (上到下), LR (左到右), BT (下到上), RL (右到左)

    Returns:
        Mermaid 格式的字符串
    """
    lines = [f"graph {direction}"]

    # 用于存储已添加的节点，避免重复
    nodes: set[str] = set()

    # 添加边
    for caller, callee in graph.edges:
        # 转义特殊字符，处理长名称
        caller_id = _sanitize_id(caller)
        callee_id = _sanitize_id(callee)
        caller_label = _format_label(caller)
        callee_label = _format_label(callee)

        # 添加节点定义（如果尚未添加）
        if caller not in nodes:
            lines.append(f'    {caller_id}["{caller_label}"]')
            nodes.add(caller)
        if callee not in nodes:
            lines.append(f'    {callee_id}["{callee_label}"]')
            nodes.add(callee)

        # 添加边
        lines.append(f"    {caller_id} --> {callee_id}")

    return "\n".join(lines)


def _sanitize_id(name: str) -> str:
    """
    将名称转换为有效的 Mermaid 节点 ID

    Args:
        name: 原始名称

    Returns:
        有效的节点 ID
    """
    # 替换特殊字符为下划线
    return name.replace(".", "_").replace("-", "_").replace(" ", "_")


def _format_label(name: str) -> str:
    """
    格式化节点标签，处理长名称

    Args:
        name: 原始名称

    Returns:
        格式化后的标签
    """
    # 如果名称太长，只保留类名.方法名
    if "." in name:
        parts = name.split(".")
        if len(parts) > 2:
            # 只保留最后两部分：ClassName.methodName
            return f"{parts[-2]}.{parts[-1]}"
    return name


def to_mermaid_flowchart(graph: CallGraph, direction: str = "TD") -> str:
    """
    将 CallGraph 转换为 Mermaid Flowchart 格式（带样式）

    Args:
        graph: CallGraph 实例
        direction: 图方向

    Returns:
        Mermaid Flowchart 格式的字符串
    """
    lines = [f"flowchart {direction}"]

    nodes: set[str] = set()

    for caller, callee in graph.edges:
        caller_id = _sanitize_id(caller)
        callee_id = _sanitize_id(callee)
        caller_label = _format_label(caller)
        callee_label = _format_label(callee)

        if caller not in nodes:
            lines.append(f'    {caller_id}["{caller_label}"]')
            nodes.add(caller)
        if callee not in nodes:
            lines.append(f'    {callee_id}["{callee_label}"]')
            nodes.add(callee)

        lines.append(f"    {caller_id} --> {callee_id}")

    return "\n".join(lines)
