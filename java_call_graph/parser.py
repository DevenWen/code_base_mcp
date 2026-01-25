"""Java file parser using javalang library."""

from typing import Optional
import javalang


def parse_java_file(file_path: str) -> Optional[javalang.tree.CompilationUnit]:
    """
    解析 Java 源文件，返回 AST（抽象语法树）

    Args:
        file_path: Java 源文件路径

    Returns:
        CompilationUnit 对象，如果解析失败返回 None
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            java_code = f.read()
        return javalang.parse.parse(java_code)
    except (
        javalang.parser.JavaSyntaxError,
        FileNotFoundError,
        UnicodeDecodeError,
    ) as e:
        print(f"解析文件失败 {file_path}: {e}")
        return None


def parse_java_code(java_code: str) -> Optional[javalang.tree.CompilationUnit]:
    """
    解析 Java 代码字符串，返回 AST

    Args:
        java_code: Java 源代码字符串

    Returns:
        CompilationUnit 对象，如果解析失败返回 None
    """
    try:
        return javalang.parse.parse(java_code)
    except javalang.parser.JavaSyntaxError as e:
        print(f"解析代码失败: {e}")
        return None
