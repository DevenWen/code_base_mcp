"""Extract method calls from Java AST nodes."""

from typing import List
import javalang

from java_call_graph.models import CallType, MethodCall


def determine_call_type(qualifier: str | None) -> CallType:
    """
    根据 qualifier 判断调用类型

    Args:
        qualifier: 方法调用的限定符

    Returns:
        CallType 枚举值
    """
    if qualifier is None or qualifier == "":
        return CallType.THIS
    if qualifier == "this":
        return CallType.THIS
    if qualifier == "super":
        return CallType.SUPER
    # 首字母大写通常表示类名（静态调用）
    if qualifier[0].isupper():
        return CallType.STATIC
    # 其他情况为实例调用
    return CallType.INSTANCE


def extract_method_calls(
    method_node: javalang.tree.MethodDeclaration,
) -> List[MethodCall]:
    """
    从方法声明节点中提取所有方法调用

    Args:
        method_node: MethodDeclaration AST 节点

    Returns:
        MethodCall 对象列表
    """
    calls: List[MethodCall] = []

    # 遍历方法体内的所有 MethodInvocation 节点
    for _, call_node in method_node.filter(javalang.tree.MethodInvocation):
        qualifier = _extract_qualifier(call_node)
        method_name = call_node.member
        call_type = determine_call_type(qualifier)

        calls.append(
            MethodCall(
                qualifier=qualifier, method_name=method_name, call_type=call_type
            )
        )

    return calls


def _extract_qualifier(call_node: javalang.tree.MethodInvocation) -> str | None:
    """
    提取方法调用的 qualifier

    Args:
        call_node: MethodInvocation AST 节点

    Returns:
        qualifier 字符串或 None
    """
    qualifier = call_node.qualifier

    # qualifier 可能是字符串、MemberReference 或其他节点类型
    if qualifier is None:
        return None
    if isinstance(qualifier, str):
        return qualifier
    if hasattr(qualifier, "member"):
        # 处理链式调用的情况 a.b.method()
        return qualifier.member
    if hasattr(qualifier, "name"):
        return qualifier.name

    return str(qualifier)
