"""Data models for Java Call Graph Analyzer."""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Tuple, Optional
import json


class CallType(Enum):
    """调用类型枚举"""

    THIS = "THIS"  # 本类方法调用 validate() 或 this.validate()
    SUPER = "SUPER"  # 父类方法调用 super.onCreate()
    STATIC = "STATIC"  # 静态方法调用 Math.abs(), Logger.info()
    INSTANCE = "INSTANCE"  # 实例方法调用 userService.save()


@dataclass
class MethodCall:
    """表示一次方法调用"""

    qualifier: Optional[str]  # 调用限定符（对象名/类名）
    method_name: str  # 被调用的方法名
    call_type: CallType  # 调用类型

    def to_dict(self) -> dict:
        return {
            "qualifier": self.qualifier,
            "method_name": self.method_name,
            "call_type": self.call_type.value,
        }

    @property
    def full_name(self) -> str:
        """返回完整调用名称 qualifier.method_name"""
        if self.qualifier:
            return f"{self.qualifier}.{self.method_name}"
        return self.method_name


@dataclass
class MethodInfo:
    """表示一个方法定义"""

    class_name: str  # 所属类名
    method_name: str  # 方法名
    calls: List[MethodCall] = field(default_factory=list)  # 该方法内的所有调用

    @property
    def full_name(self) -> str:
        """返回完整名称 class_name.method_name"""
        return f"{self.class_name}.{self.method_name}"

    def to_dict(self) -> dict:
        return {
            "class_name": self.class_name,
            "method_name": self.method_name,
            "full_name": self.full_name,
            "calls": [call.to_dict() for call in self.calls],
        }


@dataclass
class CallGraph:
    """表示整个调用图"""

    methods: Dict[str, MethodInfo] = field(default_factory=dict)  # 所有方法定义
    edges: List[Tuple[str, str]] = field(
        default_factory=list
    )  # 调用边 (caller, callee)

    def add_method(self, method: MethodInfo) -> None:
        """添加方法到调用图"""
        self.methods[method.full_name] = method

    def add_edge(self, caller: str, callee: str) -> None:
        """添加调用边"""
        self.edges.append((caller, callee))

    def to_dict(self) -> dict:
        return {
            "methods": {k: v.to_dict() for k, v in self.methods.items()},
            "edges": self.edges,
        }

    def to_json(self, indent: int = 2) -> str:
        """输出 JSON 格式"""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


@dataclass
class ScanConfig:
    """
    扫描配置

    include_patterns 和 exclude_patterns 统一作用于完整路径：
    - 类级别: "com.example.service.*" 匹配 com.example.service.UserService
    - 方法级别: "*.util.*" 匹配 com.example.util.JsonUtil.safeToJSONString

    优先级: exclude_patterns > include_patterns
    即：先检查是否被排除，再检查是否被包含
    """

    include_patterns: List[str] = field(
        default_factory=list
    )  # 包含规则 ["com.example.service.*"]
    exclude_patterns: List[str] = field(
        default_factory=list
    )  # 排除规则 ["*.util.*", "*.get*", "*.set*"]
    interface_impl_map: Dict[str, str] = field(
        default_factory=dict
    )  # 接口 -> 实现类 映射 {"UserService": "UserServiceImpl"}

    def should_include(self, full_path: str) -> bool:
        """
        检查完整路径是否应该被包含

        Args:
            full_path: 完整路径，如 "com.example.UserService" 或 "com.example.UserService.findById"

        Returns:
            True 如果应该包含
        """
        # 1. 先检查排除规则（优先级更高）
        if self._matches_any(full_path, self.exclude_patterns):
            return False

        # 2. 再检查包含规则
        if not self.include_patterns:
            return True  # 没有包含规则，默认包含所有

        return self._matches_any(full_path, self.include_patterns)

    def should_include_class(self, class_name: str) -> bool:
        """
        检查类名是否应该被包含（兼容旧接口）

        Args:
            class_name: 完整类名，如 "com.example.UserService"
        """
        return self.should_include(class_name)

    def should_include_method(self, method_full_name: str) -> bool:
        """
        检查方法是否应该被包含

        Args:
            method_full_name: 完整方法名，如 "com.example.UserService.findById"
        """
        return self.should_include(method_full_name)

    def should_exclude_call(self, callee_full_name: str) -> bool:
        """
        检查方法调用是否应该被排除

        Args:
            callee_full_name: 被调用方法的完整名称或简单名称
        """
        return self._matches_any(callee_full_name, self.exclude_patterns)

    def get_impl_for_interface(self, interface_name: str) -> Optional[str]:
        """获取接口对应的实现类（从配置）"""
        return self.interface_impl_map.get(interface_name)

    def _matches_any(self, text: str, patterns: List[str]) -> bool:
        """检查文本是否匹配任一模式"""
        return any(self._match_pattern(pattern, text) for pattern in patterns)

    @staticmethod
    def _match_pattern(pattern: str, text: str) -> bool:
        """
        通配符匹配，支持 * 和 ** 模式

        * 匹配任意字符（不包含点号的单个段）
        ** 匹配任意字符（包含点号的多个段）

        Examples:
            "com.example.*" 匹配 "com.example.UserService"
            "*.util.*" 匹配 "com.example.util.JsonUtil"
            "**.get*" 匹配 "com.example.UserService.getUserById"
        """
        import fnmatch

        # 处理 ** 模式：替换为特殊标记，fnmatch 处理后再替换回来
        if "**" in pattern:
            # ** 可以匹配任意多级（包含点）
            # 将 ** 替换为一个特殊的占位符进行处理
            pattern = pattern.replace("**", "*")

        return fnmatch.fnmatch(text, pattern)


# ============================================================
# 覆盖率相关数据模型
# ============================================================


class CoverageState(Enum):
    """覆盖状态枚举"""

    FULL = "fc"  # Full Coverage - 完全覆盖
    PARTIAL = "pc"  # Partial Coverage - 部分覆盖
    NONE = "nc"  # No Coverage - 未覆盖


@dataclass
class CoverageLine:
    """单行覆盖详情"""

    report_id: str
    package_name: str
    class_name: str
    line_number: int
    coverage_state: CoverageState
    source_code: Optional[str] = None

    def __post_init__(self):
        if isinstance(self.coverage_state, str):
            self.coverage_state = CoverageState(self.coverage_state)

    def to_dict(self) -> dict:
        return {
            "report_id": self.report_id,
            "package_name": self.package_name,
            "class_name": self.class_name,
            "line_number": self.line_number,
            "coverage_state": self.coverage_state.value,
            "source_code": self.source_code,
        }


@dataclass
class MethodCoverageResult:
    """方法覆盖率结果"""

    method_name: str
    start_line: int
    end_line: int
    total_lines: int
    covered_lines: int  # fc
    partial_lines: int  # pc
    uncovered_lines: int  # nc
    coverage_rate: float
    line_details: List[CoverageLine] = field(default_factory=list)

    @property
    def needs_test_improvement(self) -> bool:
        """判断是否需要改进测试（覆盖率<80%）"""
        return self.coverage_rate < 0.8

    def to_dict(self) -> dict:
        return {
            "method_name": self.method_name,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "total_lines": self.total_lines,
            "covered_lines": self.covered_lines,
            "partial_lines": self.partial_lines,
            "uncovered_lines": self.uncovered_lines,
            "coverage_rate": self.coverage_rate,
            "line_details": [line.to_dict() for line in self.line_details],
        }
