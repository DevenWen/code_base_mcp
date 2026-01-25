"""Scanner for Java repositories - Phase 1 entry point."""

import os
from typing import List, Optional, Dict
import javalang

from java_call_graph.call_extractor import extract_method_calls
from java_call_graph.storage import CallGraphDB
from java_call_graph.models import ScanConfig
from java_call_graph.accessor_detector import is_accessor


def scan_java_files(directory: str, config: Optional[ScanConfig] = None) -> List[str]:
    """
    递归扫描目录下的所有 .java 文件

    Args:
        directory: 扫描目录路径
        config: 扫描配置（用于过滤）

    Returns:
        .java 文件路径列表
    """
    java_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".java"):
                java_files.append(os.path.join(root, file))
    return java_files


def extract_field_type_map(
    class_node: javalang.tree.ClassDeclaration,
) -> Dict[str, str]:
    """
    从类声明中提取字段名 -> 类型名 的映射

    Args:
        class_node: ClassDeclaration AST 节点

    Returns:
        字典 {field_name: type_name}
    """
    field_map: Dict[str, str] = {}

    if class_node.fields:
        for field in class_node.fields:
            # 获取字段类型
            type_name = None
            if hasattr(field.type, "name"):
                type_name = field.type.name
            elif hasattr(field.type, "type") and hasattr(field.type.type, "name"):
                type_name = field.type.type.name

            if type_name:
                # 遍历所有声明符（一个字段声明可能有多个变量）
                for declarator in field.declarators:
                    field_map[declarator.name] = type_name

    return field_map


def resolve_qualifier(qualifier: str | None, field_map: Dict[str, str]) -> str | None:
    """
    解析 qualifier，如果是字段名则替换为实际类型

    Args:
        qualifier: 原始 qualifier
        field_map: 字段名 -> 类型名 映射

    Returns:
        解析后的 qualifier（类型名或原始值）
    """
    if qualifier is None:
        return None

    # 如果 qualifier 是已知字段，返回其类型
    if qualifier in field_map:
        return field_map[qualifier]

    return qualifier


def extract_method_source(
    file_content: str, method_node: javalang.tree.MethodDeclaration
) -> str:
    """
    从文件内容中提取方法的源代码

    Args:
        file_content: 文件完整内容
        method_node: MethodDeclaration AST 节点

    Returns:
        方法源代码字符串
    """
    if not method_node.position:
        return ""

    lines = file_content.split("\n")
    start_line = method_node.position.line - 1  # 0-indexed

    # 找到方法的结束位置（通过匹配花括号）
    brace_count = 0
    in_method = False
    end_line = start_line

    for i in range(start_line, len(lines)):
        line = lines[i]
        for char in line:
            if char == "{":
                brace_count += 1
                in_method = True
            elif char == "}":
                brace_count -= 1
                if in_method and brace_count == 0:
                    end_line = i
                    break
        if in_method and brace_count == 0:
            break

    # 提取方法源代码
    method_lines = lines[start_line : end_line + 1]
    return "\n".join(method_lines)


def scan_and_store(
    directory: str,
    db_path: str,
    config: Optional[ScanConfig] = None,
    verbose: bool = False,
) -> dict:
    """
    扫描 Java 代码仓库并将解析结果存储到数据库（优化版）

    Args:
        directory: Java 代码仓库目录
        db_path: SQLite 数据库文件路径
        config: 扫描配置
        verbose: 是否显示进度信息

    Returns:
        统计信息字典
    """
    import time

    start_time = time.time()

    if config is None:
        config = ScanConfig()

    db = CallGraphDB(db_path)
    db.clear()  # 清空旧数据

    stats = {
        "files_scanned": 0,
        "classes_found": 0,
        "methods_found": 0,
        "calls_found": 0,
        "fields_resolved": 0,
        "errors": 0,
        "parse_time": 0,
        "db_time": 0,
    }

    java_files = scan_java_files(directory, config)
    total_files = len(java_files)

    if verbose:
        print(f"找到 {total_files} 个 Java 文件，开始扫描...")

    # ============================================================
    # 阶段 1: 解析所有文件，收集数据（CPU 密集）
    # ============================================================
    parse_start = time.time()

    # 收集批量数据
    classes_batch = []  # [(name, file_path), ...]
    class_to_file = {}  # {class_name: file_path}
    fields_batch = []  # [(class_name, field_name, field_type, generic_type), ...]
    impls_batch = []  # [(interface_name, impl_class_name), ...]

    # 方法和调用需要分阶段处理（需要 class_id）
    parsed_data = []  # 存储解析后的数据

    for idx, file_path in enumerate(java_files):
        stats["files_scanned"] += 1

        if verbose and idx % 100 == 0:
            print(f"  解析进度: {idx}/{total_files} ({idx * 100 // total_files}%)")

        # 读取文件（只读一次）
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                file_content = f.read()
        except Exception:
            stats["errors"] += 1
            continue

        # 解析 AST
        try:
            tree = javalang.parse.parse(file_content)
        except Exception:
            stats["errors"] += 1
            continue

        if tree is None:
            stats["errors"] += 1
            continue

        package_name = tree.package.name if tree.package else ""

        for _, class_node in tree.filter(javalang.tree.ClassDeclaration):
            class_full_name = (
                f"{package_name}.{class_node.name}" if package_name else class_node.name
            )

            # 检查是否应该包含该类
            if not config.should_include_class(class_full_name):
                continue

            # 收集类信息
            classes_batch.append((class_full_name, file_path))
            class_to_file[class_full_name] = file_path
            stats["classes_found"] += 1

            # 提取字段类型映射
            field_map = extract_field_type_map(class_node)
            stats["fields_resolved"] += len(field_map)

            # 收集类字段
            if class_node.fields:
                for field in class_node.fields:
                    field_type = (
                        field.type.name
                        if hasattr(field.type, "name")
                        else str(field.type)
                    )
                    generic_type = None
                    if hasattr(field.type, "arguments") and field.type.arguments:
                        generic_type = (
                            field.type.arguments[0].type.name
                            if hasattr(field.type.arguments[0].type, "name")
                            else None
                        )
                    for declarator in field.declarators:
                        fields_batch.append(
                            (class_full_name, declarator.name, field_type, generic_type)
                        )

            # 收集接口实现关系
            if class_node.implements:
                for impl in class_node.implements:
                    impls_batch.append((impl.name, class_full_name))

            # 收集方法信息（存储到临时结构）
            methods_data = []
            for _, method_node in class_node.filter(javalang.tree.MethodDeclaration):
                method_name = method_node.name
                method_full_name = f"{class_full_name}.{method_name}"

                # 提取方法源代码和行号（合并计算）
                start_line = method_node.position.line if method_node.position else None
                method_source, end_line = _extract_method_with_end_line(
                    file_content, method_node
                )

                # 检测是否为简单访问器方法
                method_is_accessor = is_accessor(method_node, field_map)

                # 收集参数
                params_data = []
                if method_node.parameters:
                    for idx_p, param in enumerate(method_node.parameters):
                        param_type = (
                            param.type.name
                            if hasattr(param.type, "name")
                            else str(param.type)
                        )
                        generic_type = None
                        if hasattr(param.type, "arguments") and param.type.arguments:
                            generic_type = (
                                param.type.arguments[0].type.name
                                if hasattr(param.type.arguments[0].type, "name")
                                else None
                            )
                        params_data.append(
                            (param.name, param_type, generic_type, idx_p)
                        )

                # 收集调用
                calls_data = []
                calls = extract_method_calls(method_node)
                for call in calls:
                    resolved_qualifier = resolve_qualifier(call.qualifier, field_map)
                    # 构造完整调用路径用于过滤
                    callee_full_name = (
                        f"{resolved_qualifier}.{call.method_name}"
                        if resolved_qualifier
                        else call.method_name
                    )
                    # 使用统一的过滤规则
                    if config.should_exclude_call(callee_full_name):
                        continue
                    calls_data.append(
                        (resolved_qualifier, call.method_name, call.call_type.value)
                    )
                    stats["calls_found"] += 1

                methods_data.append(
                    {
                        "class_name": class_full_name,
                        "method_name": method_name,
                        "full_name": method_full_name,
                        "source": method_source,
                        "start_line": start_line,
                        "end_line": end_line,
                        "is_accessor": method_is_accessor,
                        "params": params_data,
                        "calls": calls_data,
                    }
                )
                stats["methods_found"] += 1

            parsed_data.append({"class_name": class_full_name, "methods": methods_data})

    stats["parse_time"] = time.time() - parse_start

    if verbose:
        print(f"  解析完成，耗时 {stats['parse_time']:.2f}s")

    # ============================================================
    # 阶段 2: 批量写入数据库（IO 密集）
    # ============================================================
    db_start = time.time()

    if verbose:
        print("  开始写入数据库...")

    # 使用持久连接进行批量写入
    with db.batch_connection():
        # 1. 批量保存类
        class_id_map = db.batch_save_classes(classes_batch)

        # 2. 批量保存字段
        if fields_batch:
            db.batch_save_class_fields(fields_batch)

        # 3. 批量保存接口实现
        if impls_batch:
            db.batch_save_interface_impls(impls_batch)

        # 4. 批量保存方法
        methods_batch = []
        for data in parsed_data:
            class_name = data["class_name"]
            class_id = class_id_map.get(class_name)
            if not class_id:
                continue
            for m in data["methods"]:
                methods_batch.append(
                    (
                        class_id,
                        m["method_name"],
                        m["full_name"],
                        m["source"],
                        m["start_line"],
                        m["end_line"],
                        1 if m["is_accessor"] else 0,
                    )
                )

        method_id_map = db.batch_save_methods(methods_batch)

        # 5. 批量保存参数
        params_batch = []
        for data in parsed_data:
            for m in data["methods"]:
                method_id = method_id_map.get(m["full_name"])
                if not method_id:
                    continue
                for param_name, param_type, generic_type, param_order in m["params"]:
                    params_batch.append(
                        (method_id, param_name, param_type, generic_type, param_order)
                    )

        if params_batch:
            db.batch_save_method_params(params_batch)

        # 6. 批量保存调用
        calls_batch = []
        for data in parsed_data:
            for m in data["methods"]:
                method_id = method_id_map.get(m["full_name"])
                if not method_id:
                    continue
                for qualifier, method_name, call_type in m["calls"]:
                    calls_batch.append((method_id, qualifier, method_name, call_type))

        if calls_batch:
            db.batch_save_calls(calls_batch)

    stats["db_time"] = time.time() - db_start
    stats["total_time"] = time.time() - start_time

    if verbose:
        print(f"  数据库写入完成，耗时 {stats['db_time']:.2f}s")
        print(f"扫描完成！总耗时 {stats['total_time']:.2f}s")
        print(
            f"  - 文件: {stats['files_scanned']}, 类: {stats['classes_found']}, 方法: {stats['methods_found']}, 调用: {stats['calls_found']}"
        )

    return stats


def _extract_method_with_end_line(
    file_content: str, method_node: javalang.tree.MethodDeclaration
) -> tuple:
    """
    从文件内容中提取方法源代码和结束行号（合并计算，避免重复遍历）

    Args:
        file_content: 文件完整内容
        method_node: MethodDeclaration AST 节点

    Returns:
        (方法源代码, 结束行号) 元组
    """
    if not method_node.position:
        return "", None

    lines = file_content.split("\n")
    start_line = method_node.position.line - 1  # 0-indexed

    brace_count = 0
    in_method = False
    end_line = start_line

    for i in range(start_line, len(lines)):
        line = lines[i]
        for char in line:
            if char == "{":
                brace_count += 1
                in_method = True
            elif char == "}":
                brace_count -= 1
                if in_method and brace_count == 0:
                    end_line = i
                    break
        if in_method and brace_count == 0:
            break

    method_lines = lines[start_line : end_line + 1]
    return "\n".join(method_lines), end_line + 1  # 返回 1-indexed 行号


def _calculate_method_end_line(
    file_content: str, method_node: javalang.tree.MethodDeclaration
) -> Optional[int]:
    """
    计算方法的结束行号

    Args:
        file_content: 文件内容
        method_node: 方法 AST 节点

    Returns:
        结束行号，如果无法计算则返回 None
    """
    if not method_node.position:
        return None

    lines = file_content.split("\n")
    start_line = method_node.position.line - 1  # 0-indexed

    brace_count = 0
    in_method = False

    for i in range(start_line, len(lines)):
        line = lines[i]
        for char in line:
            if char == "{":
                brace_count += 1
                in_method = True
            elif char == "}":
                brace_count -= 1
                if in_method and brace_count == 0:
                    return i + 1  # 返回 1-indexed

    return None


def fetch_and_save_coverage(
    db_path: str,
    report_id: str,
    base_url: str = None,
) -> dict:
    """
    获取并保存覆盖率数据

    从数据库获取所有类名，调用 coverage 模块获取覆盖数据，保存到数据库。

    Args:
        db_path: 数据库文件路径
        report_id: 覆盖率报告ID
        base_url: 覆盖率报告基础URL（可选）

    Returns:
        统计信息字典
    """
    from java_call_graph.coverage import CoverageFetcher, CoverageFetchError

    db = CallGraphDB(db_path)
    fetcher = CoverageFetcher()

    stats = {
        "classes_processed": 0,
        "lines_saved": 0,
        "errors": 0,
    }

    # 获取所有类
    classes = db.get_all_classes()

    for cls in classes:
        class_name = cls["name"]

        # 从完整类名中提取包名和简单类名
        # 例如: com.vip.csc.wos.cdn.rule.GroupPurchaseSubWoRule
        parts = class_name.rsplit(".", 1)
        if len(parts) == 2:
            package_name = parts[0]
            simple_class_name = parts[1]
        else:
            package_name = ""
            simple_class_name = class_name

        try:
            # 获取覆盖率数据
            if base_url:
                coverage_lines = fetcher.fetch_coverage_for_class(
                    report_id, package_name, simple_class_name, base_url
                )
            else:
                coverage_lines = fetcher.fetch_coverage_for_class(
                    report_id, package_name, simple_class_name
                )

            # 保存到数据库
            if coverage_lines:
                saved_count = db.save_coverage_details(coverage_lines)
                stats["lines_saved"] += saved_count

            stats["classes_processed"] += 1

        except CoverageFetchError as e:
            stats["errors"] += 1
            # 可以记录日志，但不中断处理
            print(f"[WARN] 获取覆盖率失败: {class_name}, 错误: {e}")

    return stats
