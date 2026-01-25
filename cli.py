#!/usr/bin/env python3
"""
Code Base MCP CLI Tool

用于扫描 Java 代码仓库并可选地获取覆盖率数据。

使用示例:
    # 只扫描代码
    uv run python cli.py --repo-id myrepo --code-path /path/to/java/code

    # 扫描代码并获取覆盖率
    uv run python cli.py --repo-id myrepo --code-path /path/to/java/code --report-id 5442474

    # 指定自定义覆盖率报告 URL
    uv run python cli.py --repo-id myrepo --code-path /path/to/java/code --report-id 5442474 --base-url http://example.com/coverage/
"""

import argparse
import sys
from pathlib import Path

from java_call_graph.scanner import scan_and_store, fetch_and_save_coverage
from java_call_graph.models import ScanConfig


def create_parser() -> argparse.ArgumentParser:
    """创建命令行参数解析器"""
    parser = argparse.ArgumentParser(
        prog="code-base-cli",
        description="扫描 Java 代码仓库并获取覆盖率数据",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s --repo-id myrepo --code-path /path/to/java/code
  %(prog)s --repo-id myrepo --code-path /path/to/java/code --report-id 5442474
  %(prog)s --repo-id myrepo --code-path /path/to/java/code --report-id 5442474 --include "com.vip.*"
        """,
    )

    # 必需参数
    parser.add_argument(
        "--code-path",
        required=True,
        help="Java 代码仓库目录路径",
    )

    # 可选参数
    parser.add_argument(
        "--repo-id",
        help="仓库 ID，用于生成数据库文件名 (dbs/{repo_id}.db)，默认使用 code-path 的目录名",
    )
    parser.add_argument(
        "--report-id",
        help="覆盖率报告 ID（可选，如果提供则会获取覆盖率数据）",
    )
    parser.add_argument(
        "--base-url",
        default="http://qa.tools.vipshop.com/coverage/server/coverage/static/report/",
        help="覆盖率报告基础 URL（默认为内部服务器地址）",
    )

    # 扫描配置
    parser.add_argument(
        "--include",
        action="append",
        dest="include_patterns",
        metavar="PATTERN",
        help="包含的包模式，可多次使用 (例如: --include 'com.vip.csc.wos.*')",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        dest="exclude_patterns",
        metavar="PATTERN",
        help="排除的包模式，可多次使用 (例如: --exclude 'com.vip.csc.wos.util.*')",
    )

    # 其他选项
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="显示详细进度信息",
    )

    return parser


def print_scan_stats(stats: dict) -> None:
    """打印扫描统计信息"""
    print("\n" + "=" * 60)
    print("📊 代码扫描结果")
    print("=" * 60)
    print(f"  📁 扫描文件数: {stats.get('files_scanned', 0)}")
    print(f"  📦 发现类数量: {stats.get('classes_found', 0)}")
    print(f"  🔧 发现方法数: {stats.get('methods_found', 0)}")
    print(f"  📞 发现调用数: {stats.get('calls_found', 0)}")
    print(f"  🔗 解析字段数: {stats.get('fields_resolved', 0)}")
    print(f"  ❌ 错误数量: {stats.get('errors', 0)}")
    print("-" * 60)
    print(f"  ⏱️  解析耗时: {stats.get('parse_time', 0):.2f}s")
    print(f"  💾 写入耗时: {stats.get('db_time', 0):.2f}s")
    print(f"  ⏰ 总计耗时: {stats.get('total_time', 0):.2f}s")
    print("=" * 60)


def print_coverage_stats(stats: dict) -> None:
    """打印覆盖率统计信息"""
    print("\n" + "=" * 60)
    print("📈 覆盖率获取结果")
    print("=" * 60)
    print(f"  📦 处理类数量: {stats.get('classes_processed', 0)}")
    print(f"  📝 保存行数量: {stats.get('lines_saved', 0)}")
    print(f"  ❌ 错误数量: {stats.get('errors', 0)}")
    print("=" * 60)


def main() -> int:
    """CLI 主入口"""
    parser = create_parser()
    args = parser.parse_args()

    # 验证代码路径
    code_path = Path(args.code_path)
    if not code_path.exists():
        print(f"❌ 错误: 代码路径不存在: {code_path}", file=sys.stderr)
        return 1

    if not code_path.is_dir():
        print(f"❌ 错误: 代码路径不是目录: {code_path}", file=sys.stderr)
        return 1

    # 确定 repo_id（如果未指定，使用 code_path 的目录名）
    repo_id = args.repo_id or code_path.name

    # 确保 dbs 目录存在
    dbs_dir = Path(__file__).parent / "dbs"
    dbs_dir.mkdir(exist_ok=True)

    # 生成数据库路径
    db_path = dbs_dir / f"{repo_id}.db"

    print("\n🚀 Code Base MCP CLI")
    print(f"   仓库 ID: {repo_id}")
    print(f"   代码路径: {code_path}")
    print(f"   数据库: {db_path}")
    if args.report_id:
        print(f"   覆盖率报告 ID: {args.report_id}")

    # 构建扫描配置
    config = ScanConfig(
        include_patterns=args.include_patterns or [],
        exclude_patterns=args.exclude_patterns or [],
    )

    if args.include_patterns:
        print(f"   包含模式: {args.include_patterns}")
    if args.exclude_patterns:
        print(f"   排除模式: {args.exclude_patterns}")

    # ============================================================
    # 执行 1: 扫描代码
    # ============================================================
    print("\n⏳ 正在扫描代码...")

    try:
        scan_stats = scan_and_store(
            directory=str(code_path),
            db_path=str(db_path),
            config=config,
            verbose=args.verbose,
        )
        print_scan_stats(scan_stats)
    except Exception as e:
        print(f"❌ 扫描失败: {e}", file=sys.stderr)
        return 1

    # ============================================================
    # 执行 2: 获取覆盖率数据（如果提供了 report_id）
    # ============================================================
    if args.report_id:
        print("\n⏳ 正在获取覆盖率数据...")

        try:
            coverage_stats = fetch_and_save_coverage(
                db_path=str(db_path),
                report_id=args.report_id,
                base_url=args.base_url,
            )
            print_coverage_stats(coverage_stats)
        except Exception as e:
            print(f"❌ 获取覆盖率失败: {e}", file=sys.stderr)
            return 1

    print("\n✅ 完成！")  # noqa: F541
    return 0


if __name__ == "__main__":
    sys.exit(main())
