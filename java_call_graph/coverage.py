"""
覆盖率数据获取和解析模块
负责从 HTML 覆盖率报告中提取覆盖详情（纯解析，不涉及数据库操作）
"""

from typing import List
from bs4 import BeautifulSoup
import requests

from java_call_graph.models import CoverageLine, CoverageState


class CoverageFetchError(Exception):
    """覆盖率获取异常"""

    pass


class CoverageFetcher:
    """覆盖率数据获取和解析类"""

    DEFAULT_BASE_URL = (
        "http://qa.tools.vipshop.com/coverage/server/coverage/static/report/"
    )

    def fetch_coverage_for_class(
        self,
        report_id: str,
        package_name: str,
        class_name: str,
        base_url: str = None,
    ) -> List[CoverageLine]:
        """
        获取单个类的覆盖率详情

        Args:
            report_id: 覆盖率报告ID（如：5442474）
            package_name: Java包名（如：com.vip.csc.wos.cdn.rule.special）
            class_name: 类名（如：GroupPurchaseSubWoRule）
            base_url: 覆盖率报告基础URL

        Returns:
            List[CoverageLine]: 覆盖详情列表

        Raises:
            CoverageFetchError: 获取或解析失败时抛出
        """
        if base_url is None:
            base_url = self.DEFAULT_BASE_URL

        # 拼接URL
        class_file_name = class_name.replace(".java", "") + ".java.html"
        url = f"{base_url}{report_id}/{package_name}/{class_file_name}"

        # 获取HTML内容
        html_content = self._fetch_html(url)

        # 解析HTML，提取覆盖状态
        return self._parse_html_coverage(
            html_content, class_name, report_id, package_name
        )

    def _fetch_html(self, url: str) -> str:
        """
        获取HTML内容

        Args:
            url: 目标URL

        Returns:
            HTML内容字符串

        Raises:
            CoverageFetchError: 请求失败时抛出
        """
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            raise CoverageFetchError(f"获取覆盖率报告失败: {url}, 错误: {e}")

    def fetch_from_local_file(
        self,
        file_path: str,
        report_id: str,
        package_name: str,
        class_name: str,
    ) -> List[CoverageLine]:
        """
        从本地文件解析覆盖率（用于测试或离线模式）

        Args:
            file_path: 本地HTML文件路径
            report_id: 报告ID
            package_name: 包名
            class_name: 类名

        Returns:
            List[CoverageLine]: 覆盖详情列表
        """
        with open(file_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        return self._parse_html_coverage(
            html_content, class_name, report_id, package_name
        )

    def _parse_html_coverage(
        self,
        html: str,
        class_name: str,
        report_id: str,
        package_name: str,
    ) -> List[CoverageLine]:
        """
        核心解析逻辑：解析HTML覆盖率报告

        解析规则：
        - 完全覆盖 (fc)：<span class="fc" id="L123">code</span>
        - 部分覆盖 (pc)：<span class="pc" id="L123">code</span>
        - 未覆盖 (nc)：<span class="nc" id="L123">code</span>

        Args:
            html: HTML内容
            class_name: 类名
            report_id: 报告ID
            package_name: 包名

        Returns:
            List[CoverageLine]: 覆盖详情列表
        """
        soup = BeautifulSoup(html, "html.parser")
        results = []

        # 查找所有覆盖状态标记
        coverage_elements = soup.select(
            'span[class="fc"], span[class="pc"], span[class="nc"]'
        )

        for element in coverage_elements:
            # 提取行号：从 id="L123" 提取 123
            line_id = element.get("id")
            if not line_id or not line_id.startswith("L"):
                continue

            try:
                line_number = int(line_id[1:])  # 去掉 'L' 前缀
            except ValueError:
                continue

            # 提取覆盖状态
            css_class = element.get("class")
            if not css_class:
                continue
            coverage_state = css_class[0]  # fc, pc, nc

            # 提取源码
            source_code = element.get_text(strip=True)

            results.append(
                CoverageLine(
                    report_id=report_id,
                    package_name=package_name,
                    class_name=class_name,
                    line_number=line_number,
                    coverage_state=CoverageState(coverage_state),
                    source_code=source_code,
                )
            )

        return results
