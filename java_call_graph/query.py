"""Query interface for call graph - Phase 2 entry point."""

from typing import List, Optional, Set, Dict, Tuple
from java_call_graph.storage import CallGraphDB
from java_call_graph.models import (
    CallGraph,
    MethodInfo,
    MethodCall,
    CallType,
    MethodCoverageResult,
)


def resolve_interface_to_impl(
    qualifier: str,
    db: CallGraphDB,
    interface_impl_map: Optional[Dict[str, str]] = None,
) -> str:
    """
    解析接口到实现类

    Args:
        qualifier: 类名（可能是接口）
        db: 数据库连接
        interface_impl_map: 用户配置的接口 -> 实现类映射

    Returns:
        解析后的类名（实现类或原始值）
    """
    # 1. 优先使用配置映射
    if interface_impl_map and qualifier in interface_impl_map:
        return interface_impl_map[qualifier]

    # 2. 尝试自动匹配唯一实现类
    impl = db.get_single_impl_for_interface(qualifier)
    if impl:
        return impl

    # 3. 返回原始值
    return qualifier


def get_call_graph(
    db_path: str,
    method_name: str,
    depth: int = 3,
    interface_impl_map: Optional[Dict[str, str]] = None,
    only_known_methods: bool = True,
    exclude_accessors: bool = False,
) -> CallGraph:
    """
    查询指定方法的调用图

    Args:
        db_path: 数据库文件路径
        method_name: 方法名（支持 Class.method 格式或仅方法名）
        depth: 调用深度限制，默认 3 层
        interface_impl_map: 接口 -> 实现类 映射配置
        only_known_methods: 是否只输出数据库中已知的方法（过滤 JDK 等外部方法）
        exclude_accessors: 是否排除简单访问器方法 (Getter/Setter)

    Returns:
        CallGraph 对象
    """
    db = CallGraphDB(db_path)
    graph = CallGraph()
    visited: Set[str] = set()

    def _find_method(method_full_name: str) -> Optional[dict]:
        """查找方法，返回方法信息或 None"""
        method = db.get_method_by_name(method_full_name)
        if method:
            return method
        # 尝试模糊匹配
        methods = db.get_method_by_name_pattern(f"%{method_full_name}")
        if methods:
            return methods[0]
        return None

    def _is_accessor_method(method_full_name: str) -> bool:
        """检查方法是否为访问器方法"""
        method = _find_method(method_full_name)
        if method and method.get("is_accessor"):
            return True
        return False

    def _resolve_this_call(caller_class: str, callee_method: str) -> str:
        """
        解析 THIS 类型调用，自动索引到当前类

        Args:
            caller_class: 调用者所属类的完整名称
            callee_method: 被调用方法名

        Returns:
            完整的方法名 (Class.method)
        """
        return f"{caller_class}.{callee_method}"

    def _build_graph(current_method: str, current_depth: int, caller_class: str = ""):
        """递归构建调用图"""
        if current_depth > depth or current_method in visited:
            return

        visited.add(current_method)

        # 查找方法
        method = _find_method(current_method)
        if not method:
            return

        # 如果启用了访问器过滤，且当前方法是访问器，跳过
        if exclude_accessors and method.get("is_accessor"):
            return

        # 获取当前方法所属的类
        current_class = (
            method["full_name"].rsplit(".", 1)[0] if "." in method["full_name"] else ""
        )

        # 获取该方法的所有调用
        calls = db.get_calls_by_caller(method["id"])

        method_calls = []
        for call in calls:
            call_type = CallType(call["call_type"])
            callee_method_name = call["callee_method"]

            # 解析 qualifier
            resolved_qualifier = call["callee_qualifier"]

            # 改进点 2: THIS 类型调用，自动索引到当前类
            if call_type == CallType.THIS:
                resolved_qualifier = current_class
                callee_full = _resolve_this_call(current_class, callee_method_name)
            else:
                # 解析接口到实现类
                if resolved_qualifier:
                    resolved_qualifier = resolve_interface_to_impl(
                        resolved_qualifier, db, interface_impl_map
                    )
                callee_full = (
                    f"{resolved_qualifier}.{callee_method_name}"
                    if resolved_qualifier
                    else callee_method_name
                )

            # 改进点 1: 只输出数据库中已知的方法
            if only_known_methods:
                callee_exists = _find_method(callee_full) is not None
                if not callee_exists:
                    # 跳过数据库中不存在的方法（JDK 方法等）
                    continue

            # 如果启用了访问器过滤，跳过访问器方法的调用
            if exclude_accessors and _is_accessor_method(callee_full):
                continue

            method_call = MethodCall(
                qualifier=resolved_qualifier,
                method_name=callee_method_name,
                call_type=call_type,
            )
            method_calls.append(method_call)

            # 添加边
            callee_name = method_call.full_name
            graph.add_edge(method["full_name"], callee_name)

            # 改进点 3: 递归查找时检查是否已访问（避免循环）
            if callee_full not in visited:
                _build_graph(callee_full, current_depth + 1, current_class)

        # 将方法添加到图中
        method_info = MethodInfo(
            class_name=current_class,
            method_name=method["name"],
            calls=method_calls,
        )
        graph.add_method(method_info)

    _build_graph(method_name, 1)
    return graph


def get_callers(db_path: str, method_name: str, depth: int = 1) -> List[str]:
    """
    查询谁调用了指定方法

    Args:
        db_path: 数据库文件路径
        method_name: 方法名（格式：qualifier.method 或仅 method）
        depth: 查询深度

    Returns:
        调用者方法名列表
    """
    db = CallGraphDB(db_path)
    result: List[str] = []
    visited: Set[str] = set()

    def _find_callers(target: str, current_depth: int):
        if current_depth > depth or target in visited:
            return

        visited.add(target)

        # 解析 qualifier 和 method
        if "." in target:
            qualifier, method = target.rsplit(".", 1)
        else:
            qualifier, method = None, target

        callers = db.get_callers_of_method(qualifier, method)
        for caller in callers:
            caller_name = caller["full_name"]
            if caller_name not in result:
                result.append(caller_name)
            _find_callers(caller_name, current_depth + 1)

    _find_callers(method_name, 1)
    return result


def get_callees(db_path: str, method_name: str, depth: int = 1) -> List[str]:
    """
    查询指定方法调用了谁

    Args:
        db_path: 数据库文件路径
        method_name: 完整方法名（Class.method）
        depth: 查询深度

    Returns:
        被调用方法名列表
    """
    db = CallGraphDB(db_path)
    result: List[str] = []
    visited: Set[str] = set()

    def _find_callees(current: str, current_depth: int):
        if current_depth > depth or current in visited:
            return

        visited.add(current)

        method = db.get_method_by_name(current)
        if not method:
            methods = db.get_method_by_name_pattern(f"%{current}%")
            if methods:
                method = methods[0]
            else:
                return

        calls = db.get_calls_by_caller(method["id"])
        for call in calls:
            if call["callee_qualifier"]:
                callee_name = f"{call['callee_qualifier']}.{call['callee_method']}"
            else:
                callee_name = call["callee_method"]

            if callee_name not in result:
                result.append(callee_name)

            _find_callees(callee_name, current_depth + 1)

    _find_callees(method_name, 1)
    return result


# Java 类型到 JSON Schema 类型的映射
JAVA_TO_JSON_SCHEMA_TYPE = {
    # 基本类型
    "String": "string",
    "int": "integer",
    "Integer": "integer",
    "long": "integer",
    "Long": "integer",
    "short": "integer",
    "Short": "integer",
    "byte": "integer",
    "Byte": "integer",
    "float": "number",
    "Float": "number",
    "double": "number",
    "Double": "number",
    "boolean": "boolean",
    "Boolean": "boolean",
    "BigDecimal": "number",
    "BigInteger": "integer",
    # 日期时间
    "Date": "string",
    "LocalDate": "string",
    "LocalDateTime": "string",
    "LocalTime": "string",
    "Timestamp": "string",
    # 集合类型
    "List": "array",
    "ArrayList": "array",
    "Set": "array",
    "HashSet": "array",
    "Collection": "array",
    # Map 类型
    "Map": "object",
    "HashMap": "object",
    # 其他
    "Object": "object",
    "void": "null",
}


def _java_type_to_json_schema(
    java_type: str,
    generic_type: Optional[str],
    db: CallGraphDB,
    visited: Set[str],
) -> dict:
    """
    将 Java 类型转换为 JSON Schema

    Args:
        java_type: Java 类型名
        generic_type: 泛型类型
        db: 数据库连接
        visited: 已访问的类型（避免循环引用）

    Returns:
        JSON Schema 字典
    """
    # 检查是否为基本类型
    if java_type in JAVA_TO_JSON_SCHEMA_TYPE:
        schema_type = JAVA_TO_JSON_SCHEMA_TYPE[java_type]

        if schema_type == "array" and generic_type:
            # 处理数组元素类型
            items_schema = _java_type_to_json_schema(generic_type, None, db, visited)
            return {"type": "array", "items": items_schema}

        return {"type": schema_type}

    # 检查是否为 DTO 类型（需要递归解析）
    if java_type in visited:
        # 避免循环引用
        return {"$ref": f"#/definitions/{java_type}"}

    # 尝试从数据库查找类字段
    visited.add(java_type)

    # 先精确匹配
    fields = db.get_class_fields(java_type)
    if not fields:
        # 尝试模糊匹配
        fields = db.get_class_fields_by_pattern(f"%{java_type}")

    if fields:
        # 是 DTO 类型，递归解析
        properties = {}
        for field in fields:
            field_schema = _java_type_to_json_schema(
                field["field_type"],
                field["generic_type"],
                db,
                visited.copy(),
            )
            properties[field["field_name"]] = field_schema

        return {
            "type": "object",
            "properties": properties,
        }

    # 未知类型，返回 object
    return {"type": "object", "description": f"Unknown type: {java_type}"}


def get_method_json_schema(db_path: str, method_name: str) -> dict:
    """
    根据方法参数签名生成 JSON Schema

    Args:
        db_path: 数据库文件路径
        method_name: 方法完整名称（Class.method）

    Returns:
        JSON Schema 字典
    """
    db = CallGraphDB(db_path)

    # 查找方法
    method = db.get_method_by_name(method_name)
    if not method:
        methods = db.get_method_by_name_pattern(f"%{method_name}")
        if methods:
            method = methods[0]
        else:
            return {"error": f"Method not found: {method_name}"}

    # 获取方法参数
    params = db.get_method_params(method["id"])

    if not params:
        return {
            "type": "object",
            "properties": {},
            "description": f"Method {method_name} has no parameters",
        }

    # 构建 JSON Schema
    properties = {}
    required = []

    for param in params:
        visited: Set[str] = set()
        param_schema = _java_type_to_json_schema(
            param["param_type"],
            param["generic_type"],
            db,
            visited,
        )
        properties[param["param_name"]] = param_schema
        required.append(param["param_name"])

    return {
        "type": "object",
        "properties": properties,
        "required": required,
    }


def get_method_by_name_with_coverage(
    db_path: str,
    method_name: str,
    report_id: str,
) -> Tuple[Optional[dict], Optional[MethodCoverageResult]]:
    """
    查询方法信息并附带覆盖率数据

    Args:
        db_path: 数据库文件路径
        method_name: 方法完整名称（Class.method）
        report_id: 覆盖率报告ID

    Returns:
        (method_info, coverage_result) 元组
        - method_info: 方法信息字典，如果未找到则为 None
        - coverage_result: 覆盖率结果，如果没有覆盖率数据则为 None
    """
    db = CallGraphDB(db_path)

    # 查找方法
    method = db.get_method_by_name(method_name)
    if not method:
        # 尝试模糊匹配
        methods = db.get_method_by_name_pattern(f"%{method_name}")
        if methods:
            method = methods[0]
        else:
            return None, None

    # 检查是否有行号信息
    start_line = method.get("start_line")
    end_line = method.get("end_line")

    if start_line is None or end_line is None:
        return method, None

    # 从完整类名中提取简单类名
    full_name = method["full_name"]
    class_name = full_name.rsplit(".", 1)[0] if "." in full_name else ""
    simple_class_name = (
        class_name.rsplit(".", 1)[-1] if "." in class_name else class_name
    )

    # 获取覆盖率数据
    coverage_lines = db.get_method_coverage(
        report_id, simple_class_name, start_line, end_line
    )

    if not coverage_lines:
        return method, None

    # 统计覆盖率
    covered_count = sum(
        1 for line in coverage_lines if line.coverage_state.value == "fc"
    )
    partial_count = sum(
        1 for line in coverage_lines if line.coverage_state.value == "pc"
    )
    uncovered_count = sum(
        1 for line in coverage_lines if line.coverage_state.value == "nc"
    )
    total_count = len(coverage_lines)

    # 计算覆盖率 (fc + pc*0.5) / total
    coverage_rate = 0.0
    if total_count > 0:
        coverage_rate = (covered_count + partial_count * 0.5) / total_count

    coverage_result = MethodCoverageResult(
        method_name=method["full_name"],
        start_line=start_line,
        end_line=end_line,
        total_lines=total_count,
        covered_lines=covered_count,
        partial_lines=partial_count,
        uncovered_lines=uncovered_count,
        coverage_rate=round(coverage_rate, 3),
        line_details=coverage_lines,
    )

    return method, coverage_result
