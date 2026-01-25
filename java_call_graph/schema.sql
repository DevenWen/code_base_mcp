-- Java Call Graph Database Schema
-- 所有表结构定义

-- classes 表：类信息
CREATE TABLE IF NOT EXISTS classes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    package_name TEXT,
    file_path TEXT NOT NULL,
    UNIQUE(name, file_path)
);

-- methods 表：方法信息
CREATE TABLE IF NOT EXISTS methods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    class_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    full_name TEXT NOT NULL,
    source_code TEXT,
    start_line INTEGER,
    end_line INTEGER,
    is_accessor INTEGER DEFAULT 0,  -- 是否为简单访问器方法 (0/1)
    FOREIGN KEY (class_id) REFERENCES classes(id),
    UNIQUE(full_name)
);

-- calls 表：调用关系
CREATE TABLE IF NOT EXISTS calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    caller_id INTEGER NOT NULL,
    callee_qualifier TEXT,
    callee_method TEXT NOT NULL,
    call_type TEXT NOT NULL,
    FOREIGN KEY (caller_id) REFERENCES methods(id)
);

-- interface_impls 表：接口 -> 实现类 映射
CREATE TABLE IF NOT EXISTS interface_impls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    interface_name TEXT NOT NULL,
    impl_class_name TEXT NOT NULL,
    UNIQUE(interface_name, impl_class_name)
);

-- class_fields 表：类字段信息（用于 DTO 解析）
CREATE TABLE IF NOT EXISTS class_fields (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    class_name TEXT NOT NULL,
    field_name TEXT NOT NULL,
    field_type TEXT NOT NULL,
    generic_type TEXT,
    UNIQUE(class_name, field_name)
);

-- method_params 表：方法参数信息
CREATE TABLE IF NOT EXISTS method_params (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    method_id INTEGER NOT NULL,
    param_name TEXT NOT NULL,
    param_type TEXT NOT NULL,
    generic_type TEXT,
    param_order INTEGER NOT NULL,
    FOREIGN KEY (method_id) REFERENCES methods(id)
);

-- coverage_detail 表：覆盖率详情
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
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_methods_full_name ON methods(full_name);
CREATE INDEX IF NOT EXISTS idx_calls_caller_id ON calls(caller_id);
CREATE INDEX IF NOT EXISTS idx_calls_callee ON calls(callee_qualifier, callee_method);
CREATE INDEX IF NOT EXISTS idx_interface_impls_interface ON interface_impls(interface_name);
CREATE INDEX IF NOT EXISTS idx_class_fields_class ON class_fields(class_name);
CREATE INDEX IF NOT EXISTS idx_method_params_method ON method_params(method_id);
CREATE INDEX IF NOT EXISTS idx_coverage_detail_report ON coverage_detail(report_id, package_name, class_name);
CREATE INDEX IF NOT EXISTS idx_coverage_detail_line ON coverage_detail(report_id, class_name, line_number);
