"""SQLite storage layer for call graph data."""

import sqlite3
from typing import Optional, List
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime

from java_call_graph.models import CoverageLine


class CallGraphDB:
    """调用图数据库管理类"""

    def __init__(self, db_path: str):
        """
        初始化数据库连接

        Args:
            db_path: SQLite 数据库文件路径
        """
        self.db_path = db_path
        self._init_db()

    @contextmanager
    def _get_connection(self):
        """获取数据库连接的上下文管理器"""
        # 如果有持久连接，使用持久连接
        if hasattr(self, "_persistent_conn") and self._persistent_conn:
            yield self._persistent_conn
            return

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    @contextmanager
    def batch_connection(self):
        """
        批量操作的持久连接上下文管理器
        在此上下文内的所有操作共享同一连接，结束时统一提交
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        # 开启 WAL 模式以提高写入性能
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        self._persistent_conn = conn
        try:
            yield conn
            conn.commit()
        finally:
            self._persistent_conn = None
            conn.close()

    def _init_db(self) -> None:
        """从 schema.sql 初始化数据库表结构"""
        schema_path = Path(__file__).parent / "schema.sql"

        with self._get_connection() as conn:
            cursor = conn.cursor()

            if schema_path.exists():
                # 从 schema.sql 读取并执行
                with open(schema_path, "r", encoding="utf-8") as f:
                    schema_sql = f.read()
                cursor.executescript(schema_sql)
            else:
                # 向后兼容：如果 schema.sql 不存在，使用内联定义
                self._init_db_inline(cursor)

            # 处理 methods 表的列迁移（添加 start_line, end_line）
            self._migrate_methods_table(cursor)

    def _migrate_methods_table(self, cursor) -> None:
        """迁移 methods 表，添加新列"""
        # 检查列是否存在
        cursor.execute("PRAGMA table_info(methods)")
        columns = [row[1] for row in cursor.fetchall()]

        if "start_line" not in columns:
            cursor.execute("ALTER TABLE methods ADD COLUMN start_line INTEGER")
        if "end_line" not in columns:
            cursor.execute("ALTER TABLE methods ADD COLUMN end_line INTEGER")
        if "is_accessor" not in columns:
            cursor.execute(
                "ALTER TABLE methods ADD COLUMN is_accessor INTEGER DEFAULT 0"
            )

    def _init_db_inline(self, cursor) -> None:
        """内联定义表结构（向后兼容）"""
        # classes 表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS classes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                package_name TEXT,
                file_path TEXT NOT NULL,
                UNIQUE(name, file_path)
            )
        """)

        # methods 表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS methods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                class_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                full_name TEXT NOT NULL,
                source_code TEXT,
                start_line INTEGER,
                end_line INTEGER,
                FOREIGN KEY (class_id) REFERENCES classes(id),
                UNIQUE(full_name)
            )
        """)

        # calls 表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                caller_id INTEGER NOT NULL,
                callee_qualifier TEXT,
                callee_method TEXT NOT NULL,
                call_type TEXT NOT NULL,
                FOREIGN KEY (caller_id) REFERENCES methods(id)
            )
        """)

        # interface_impls 表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS interface_impls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                interface_name TEXT NOT NULL,
                impl_class_name TEXT NOT NULL,
                UNIQUE(interface_name, impl_class_name)
            )
        """)

        # class_fields 表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS class_fields (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                class_name TEXT NOT NULL,
                field_name TEXT NOT NULL,
                field_type TEXT NOT NULL,
                generic_type TEXT,
                UNIQUE(class_name, field_name)
            )
        """)

        # method_params 表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS method_params (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                method_id INTEGER NOT NULL,
                param_name TEXT NOT NULL,
                param_type TEXT NOT NULL,
                generic_type TEXT,
                param_order INTEGER NOT NULL,
                FOREIGN KEY (method_id) REFERENCES methods(id)
            )
        """)

        # coverage_detail 表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS coverage_detail (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_id TEXT NOT NULL,
                package_name TEXT NOT NULL,
                class_name TEXT NOT NULL,
                line_number INTEGER NOT NULL,
                coverage_state TEXT NOT NULL CHECK (coverage_state IN ('fc', 'pc', 'nc')),
                source_code TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(report_id, package_name, class_name, line_number)
            )
        """)

        # 创建索引
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_methods_full_name ON methods(full_name)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_calls_caller_id ON calls(caller_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_calls_callee ON calls(callee_qualifier, callee_method)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_interface_impls_interface ON interface_impls(interface_name)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_class_fields_class ON class_fields(class_name)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_method_params_method ON method_params(method_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_coverage_detail_report ON coverage_detail(report_id, package_name, class_name)"
        )

    def save_class(self, name: str, file_path: str) -> int:
        """
        保存类信息

        Args:
            name: 类名
            file_path: 源文件路径

        Returns:
            类 ID
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO classes (name, file_path) VALUES (?, ?)",
                (name, file_path),
            )
            cursor.execute(
                "SELECT id FROM classes WHERE name = ? AND file_path = ?",
                (name, file_path),
            )
            return cursor.fetchone()[0]

    def save_method(
        self,
        class_id: int,
        name: str,
        full_name: str,
        source_code: Optional[str] = None,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
        is_accessor: bool = False,
    ) -> int:
        """
        保存方法信息

        Args:
            class_id: 所属类 ID
            name: 方法名
            full_name: 完整名称 (class.method)
            source_code: 方法源代码
            start_line: 方法起始行号
            end_line: 方法结束行号
            is_accessor: 是否为简单访问器方法 (Getter/Setter)

        Returns:
            方法 ID
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO methods (class_id, name, full_name, source_code, start_line, end_line, is_accessor) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    class_id,
                    name,
                    full_name,
                    source_code,
                    start_line,
                    end_line,
                    1 if is_accessor else 0,
                ),
            )
            cursor.execute("SELECT id FROM methods WHERE full_name = ?", (full_name,))
            return cursor.fetchone()[0]

    def save_call(
        self,
        caller_id: int,
        callee_qualifier: Optional[str],
        callee_method: str,
        call_type: str,
    ) -> int:
        """
        保存调用关系

        Args:
            caller_id: 调用者方法 ID
            callee_qualifier: 被调用者限定符
            callee_method: 被调用方法名
            call_type: 调用类型

        Returns:
            调用记录 ID
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO calls (caller_id, callee_qualifier, callee_method, call_type) VALUES (?, ?, ?, ?)",
                (caller_id, callee_qualifier, callee_method, call_type),
            )
            return cursor.lastrowid

    def get_method_by_name(self, full_name: str) -> Optional[dict]:
        """
        根据完整名称查询方法

        Args:
            full_name: 完整名称 (class.method)

        Returns:
            方法信息字典或 None
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM methods WHERE full_name = ?", (full_name,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_method_by_name_pattern(self, pattern: str) -> List[dict]:
        """
        根据名称模式查询方法（支持 LIKE 查询）

        Args:
            pattern: 名称模式，如 'OrderService.%'

        Returns:
            方法信息列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM methods WHERE full_name LIKE ?", (pattern,))
            return [dict(row) for row in cursor.fetchall()]

    def get_calls_by_caller(self, caller_id: int) -> List[dict]:
        """
        获取某方法的所有调用

        Args:
            caller_id: 调用者方法 ID

        Returns:
            调用记录列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM calls WHERE caller_id = ?", (caller_id,))
            return [dict(row) for row in cursor.fetchall()]

    def get_callers_of_method(
        self, callee_qualifier: str, callee_method: str
    ) -> List[dict]:
        """
        获取调用某方法的所有调用者

        Args:
            callee_qualifier: 被调用者限定符
            callee_method: 被调用方法名

        Returns:
            调用者方法列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if callee_qualifier:
                cursor.execute(
                    """
                    SELECT m.* FROM methods m
                    JOIN calls c ON m.id = c.caller_id
                    WHERE c.callee_qualifier = ? AND c.callee_method = ?
                """,
                    (callee_qualifier, callee_method),
                )
            else:
                cursor.execute(
                    """
                    SELECT m.* FROM methods m
                    JOIN calls c ON m.id = c.caller_id
                    WHERE c.callee_method = ?
                """,
                    (callee_method,),
                )
            return [dict(row) for row in cursor.fetchall()]

    def save_interface_impl(self, interface_name: str, impl_class_name: str) -> int:
        """
        保存接口 -> 实现类 映射

        Args:
            interface_name: 接口名
            impl_class_name: 实现类名

        Returns:
            记录 ID
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO interface_impls (interface_name, impl_class_name) VALUES (?, ?)",
                (interface_name, impl_class_name),
            )
            return cursor.lastrowid

    def get_impls_for_interface(self, interface_name: str) -> List[str]:
        """
        获取接口的所有实现类

        Args:
            interface_name: 接口名

        Returns:
            实现类名列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT impl_class_name FROM interface_impls WHERE interface_name = ?",
                (interface_name,),
            )
            return [row[0] for row in cursor.fetchall()]

    def get_single_impl_for_interface(self, interface_name: str) -> Optional[str]:
        """
        获取接口的唯一实现类（如果只有一个）

        Args:
            interface_name: 接口名

        Returns:
            实现类名，如果没有或有多个则返回 None
        """
        impls = self.get_impls_for_interface(interface_name)
        if len(impls) == 1:
            return impls[0]
        return None

    def save_class_field(
        self,
        class_name: str,
        field_name: str,
        field_type: str,
        generic_type: Optional[str] = None,
    ) -> int:
        """
        保存类字段信息

        Args:
            class_name: 类名
            field_name: 字段名
            field_type: 字段类型
            generic_type: 泛型类型

        Returns:
            记录 ID
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO class_fields (class_name, field_name, field_type, generic_type) VALUES (?, ?, ?, ?)",
                (class_name, field_name, field_type, generic_type),
            )
            return cursor.lastrowid

    def get_class_fields(self, class_name: str) -> List[dict]:
        """
        获取类的所有字段

        Args:
            class_name: 类名

        Returns:
            字段信息列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM class_fields WHERE class_name = ?",
                (class_name,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_class_fields_by_pattern(self, pattern: str) -> List[dict]:
        """
        根据类名模式查询字段

        Args:
            pattern: 类名模式

        Returns:
            字段信息列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM class_fields WHERE class_name LIKE ?",
                (pattern,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def save_method_param(
        self,
        method_id: int,
        param_name: str,
        param_type: str,
        param_order: int,
        generic_type: Optional[str] = None,
    ) -> int:
        """
        保存方法参数信息

        Args:
            method_id: 方法 ID
            param_name: 参数名
            param_type: 参数类型
            param_order: 参数顺序
            generic_type: 泛型类型

        Returns:
            记录 ID
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO method_params (method_id, param_name, param_type, generic_type, param_order) VALUES (?, ?, ?, ?, ?)",
                (method_id, param_name, param_type, generic_type, param_order),
            )
            return cursor.lastrowid

    def get_method_params(self, method_id: int) -> List[dict]:
        """
        获取方法的所有参数

        Args:
            method_id: 方法 ID

        Returns:
            参数信息列表（按顺序）
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM method_params WHERE method_id = ? ORDER BY param_order",
                (method_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def clear(self) -> None:
        """清空所有数据"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM calls")
            cursor.execute("DELETE FROM method_params")
            cursor.execute("DELETE FROM methods")
            cursor.execute("DELETE FROM class_fields")
            cursor.execute("DELETE FROM classes")
            cursor.execute("DELETE FROM interface_impls")
            cursor.execute("DELETE FROM coverage_detail")

    # ============================================================
    # 批量写入方法（性能优化）
    # ============================================================

    def batch_save_classes(self, classes: list) -> dict:
        """
        批量保存类信息

        Args:
            classes: [(name, file_path), ...]

        Returns:
            {name: class_id} 映射
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(
                "INSERT OR IGNORE INTO classes (name, file_path) VALUES (?, ?)", classes
            )
            # 获取所有类的 ID
            result = {}
            for name, file_path in classes:
                cursor.execute(
                    "SELECT id FROM classes WHERE name = ? AND file_path = ?",
                    (name, file_path),
                )
                row = cursor.fetchone()
                if row:
                    result[name] = row[0]
            return result

    def batch_save_methods(self, methods: list) -> dict:
        """
        批量保存方法信息

        Args:
            methods: [(class_id, name, full_name, source_code, start_line, end_line, is_accessor), ...]

        Returns:
            {full_name: method_id} 映射
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(
                "INSERT OR IGNORE INTO methods (class_id, name, full_name, source_code, start_line, end_line, is_accessor) VALUES (?, ?, ?, ?, ?, ?, ?)",
                methods,
            )
            # 获取所有方法的 ID
            result = {}
            for _, _, full_name, *_ in methods:
                cursor.execute(
                    "SELECT id FROM methods WHERE full_name = ?", (full_name,)
                )
                row = cursor.fetchone()
                if row:
                    result[full_name] = row[0]
            return result

    def batch_save_calls(self, calls: list) -> int:
        """
        批量保存调用关系

        Args:
            calls: [(caller_id, callee_qualifier, callee_method, call_type), ...]

        Returns:
            插入的记录数
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(
                "INSERT INTO calls (caller_id, callee_qualifier, callee_method, call_type) VALUES (?, ?, ?, ?)",
                calls,
            )
            return len(calls)

    def batch_save_class_fields(self, fields: list) -> int:
        """
        批量保存类字段

        Args:
            fields: [(class_name, field_name, field_type, generic_type), ...]

        Returns:
            插入的记录数
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(
                "INSERT OR IGNORE INTO class_fields (class_name, field_name, field_type, generic_type) VALUES (?, ?, ?, ?)",
                fields,
            )
            return len(fields)

    def batch_save_method_params(self, params: list) -> int:
        """
        批量保存方法参数

        Args:
            params: [(method_id, param_name, param_type, generic_type, param_order), ...]

        Returns:
            插入的记录数
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(
                "INSERT INTO method_params (method_id, param_name, param_type, generic_type, param_order) VALUES (?, ?, ?, ?, ?)",
                params,
            )
            return len(params)

    def batch_save_interface_impls(self, impls: list) -> int:
        """
        批量保存接口实现关系

        Args:
            impls: [(interface_name, impl_class_name), ...]

        Returns:
            插入的记录数
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(
                "INSERT OR IGNORE INTO interface_impls (interface_name, impl_class_name) VALUES (?, ?)",
                impls,
            )
            return len(impls)

    # ============================================================
    # 覆盖率相关方法
    # ============================================================

    def save_coverage_details(self, details: List[CoverageLine]) -> int:
        """
        批量保存覆盖率详情

        Args:
            details: 覆盖详情列表

        Returns:
            int: 插入的记录数
        """
        if not details:
            return 0

        sql = """
        INSERT OR REPLACE INTO coverage_detail (
            report_id, package_name, class_name, line_number,
            coverage_state, source_code, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """

        batch_data = [
            (
                detail.report_id,
                detail.package_name,
                detail.class_name,
                detail.line_number,
                detail.coverage_state.value,
                detail.source_code,
                datetime.now(),
            )
            for detail in details
        ]

        with self._get_connection() as conn:
            conn.executemany(sql, batch_data)

        return len(batch_data)

    def get_method_coverage(
        self,
        report_id: str,
        class_name: str,
        start_line: int,
        end_line: int,
    ) -> List[CoverageLine]:
        """
        获取方法行范围内的覆盖率数据

        Args:
            report_id: 报告ID
            class_name: 类名
            start_line: 起始行
            end_line: 结束行

        Returns:
            List[CoverageLine]: 覆盖详情列表
        """
        sql = """
        SELECT report_id, package_name, class_name, line_number, coverage_state, source_code
        FROM coverage_detail
        WHERE report_id = ? AND class_name = ?
          AND line_number >= ? AND line_number <= ?
        ORDER BY line_number
        """

        results = []
        with self._get_connection() as conn:
            cursor = conn.execute(sql, (report_id, class_name, start_line, end_line))
            for row in cursor:
                results.append(
                    CoverageLine(
                        report_id=row[0],
                        package_name=row[1],
                        class_name=row[2],
                        line_number=row[3],
                        coverage_state=row[4],
                        source_code=row[5],
                    )
                )

        return results

    def delete_coverage_by_report(self, report_id: str) -> int:
        """
        删除指定报告的覆盖率数据

        Args:
            report_id: 报告ID

        Returns:
            int: 删除的记录数
        """
        sql = "DELETE FROM coverage_detail WHERE report_id = ?"

        with self._get_connection() as conn:
            cursor = conn.execute(sql, (report_id,))
            return cursor.rowcount

    def get_all_classes(self) -> List[dict]:
        """
        获取所有类信息

        Returns:
            List[dict]: 类信息列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM classes")
            return [dict(row) for row in cursor.fetchall()]
