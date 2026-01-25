"""Accessor method (Getter/Setter) detector for Java AST nodes.

基于 AST 分析方法体结构，智能识别简单的 Getter/Setter 方法，
避免仅依赖方法名前缀匹配导致的误杀问题。
"""

from typing import Dict, Optional
from javalang.tree import (
    MethodDeclaration,
    ReturnStatement,
    StatementExpression,
    Assignment,
    MemberReference,
    This,
)


def _get_field_name_from_accessor(method_name: str, prefix: str) -> Optional[str]:
    """
    从访问器方法名提取对应的字段名

    Args:
        method_name: 方法名，如 getName, setAge, isActive
        prefix: 前缀，如 get, set, is

    Returns:
        对应的字段名（camelCase），如 name, age, active
        如果不符合模式则返回 None
    """
    if not method_name.startswith(prefix):
        return None

    field_part = method_name[len(prefix) :]
    if not field_part:
        return None

    # 转换为 camelCase：getName -> name
    return field_part[0].lower() + field_part[1:]


def _has_single_return_statement(method_node: MethodDeclaration) -> bool:
    """
    检查方法体是否只有一条 return 语句

    Args:
        method_node: 方法 AST 节点

    Returns:
        True 如果方法体只有一条 return 语句
    """
    if not method_node.body:
        return False

    if len(method_node.body) != 1:
        return False

    return isinstance(method_node.body[0], ReturnStatement)


def _has_single_assignment_statement(method_node: MethodDeclaration) -> bool:
    """
    检查方法体是否只有一条赋值语句

    Args:
        method_node: 方法 AST 节点

    Returns:
        True 如果方法体只有一条赋值语句
    """
    if not method_node.body:
        return False

    if len(method_node.body) != 1:
        return False

    stmt = method_node.body[0]
    if not isinstance(stmt, StatementExpression):
        return False

    return isinstance(stmt.expression, Assignment)


def _is_simple_field_return(return_stmt: ReturnStatement) -> bool:
    """
    检查 return 语句是否只返回一个简单的字段引用

    支持的模式：
    - return name;
    - return this.name;

    Args:
        return_stmt: ReturnStatement 节点

    Returns:
        True 如果是简单字段返回
    """
    expr = return_stmt.expression
    if expr is None:
        return False

    # return name; 或 return this.name;
    if isinstance(expr, MemberReference):
        # 可能是 this.name 或直接 name
        return True

    # return this.xxx; 的另一种 AST 形式
    if isinstance(expr, This):
        return True

    return False


def is_simple_getter(method_node: MethodDeclaration, field_map: Dict[str, str]) -> bool:
    """
    判断是否为简单 Getter 方法

    识别条件：
    1. 方法名符合 getXxx 或 isXxx 模式
    2. 无参数
    3. 有返回值（非 void）
    4. 方法体只有一条 return 语句，返回字段值
    5. 对应字段存在（可选，提高准确性）

    Args:
        method_node: MethodDeclaration AST 节点
        field_map: 字段名 -> 类型名 映射

    Returns:
        True 如果是简单 Getter
    """
    name = method_node.name

    # 1. 检查方法名模式
    field_name = _get_field_name_from_accessor(name, "get")
    if field_name is None:
        field_name = _get_field_name_from_accessor(name, "is")
    if field_name is None:
        return False

    # 2. 检查无参数
    if method_node.parameters:
        return False

    # 3. 检查有返回值
    if method_node.return_type is None:
        return False
    return_type_name = getattr(method_node.return_type, "name", None)
    if return_type_name == "void":
        return False

    # 4. 检查方法体结构：只有一条 return 语句
    if not _has_single_return_statement(method_node):
        return False

    # 进一步检查 return 语句是否返回简单字段
    return_stmt = method_node.body[0]
    if not _is_simple_field_return(return_stmt):
        return False

    # 5. 检查对应字段是否存在（如果有字段映射）
    if field_map and field_name not in field_map:
        # 也尝试原始大小写
        original_field_name = name[3:] if name.startswith("get") else name[2:]
        if original_field_name not in field_map:
            return False

    return True


def is_simple_setter(method_node: MethodDeclaration, field_map: Dict[str, str]) -> bool:
    """
    判断是否为简单 Setter 方法

    识别条件：
    1. 方法名符合 setXxx 模式
    2. 恰好一个参数
    3. 返回 void 或返回 this（Builder 模式）
    4. 方法体只有一条赋值语句
    5. 对应字段存在（可选，提高准确性）

    Args:
        method_node: MethodDeclaration AST 节点
        field_map: 字段名 -> 类型名 映射

    Returns:
        True 如果是简单 Setter
    """
    name = method_node.name

    # 1. 检查方法名模式
    field_name = _get_field_name_from_accessor(name, "set")
    if field_name is None:
        return False

    # 2. 检查恰好一个参数
    if not method_node.parameters or len(method_node.parameters) != 1:
        return False

    # 3. 检查返回类型：void 或 this（Builder 模式也可接受）
    # 这里放宽限制，允许任意返回类型

    # 4. 检查方法体结构：只有一条赋值语句
    if not _has_single_assignment_statement(method_node):
        return False

    # 5. 检查对应字段是否存在（如果有字段映射）
    if field_map and field_name not in field_map:
        # 也尝试原始大小写
        original_field_name = name[3:]  # 去掉 set
        if original_field_name not in field_map:
            return False

    return True


def is_accessor(method_node: MethodDeclaration, field_map: Dict[str, str]) -> bool:
    """
    综合判断是否为访问器方法（Getter 或 Setter）

    Args:
        method_node: MethodDeclaration AST 节点
        field_map: 字段名 -> 类型名 映射

    Returns:
        True 如果是 Getter 或 Setter
    """
    return is_simple_getter(method_node, field_map) or is_simple_setter(
        method_node, field_map
    )
