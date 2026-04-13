"""网络请求记录器 - 每步独立 tracing，解析并分类网络请求

设计思路：
1. 在每一步测试执行前后 start/stop Playwright tracing
2. 解析 .network 文件中的 JSON Lines 数据
3. 根据 mimeType、method、URL 模式对请求分类
4. 保存为 network_trace.json，前端按步骤折叠展示

注意：Playwright MCP 的 trace 文件保存在项目的 .playwright-mcp/traces 目录
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class NetworkRecorder:
    """网络请求记录器 - 每步独立 tracing，解析并分类网络请求"""

    # 默认显示的类别（前端默认只显示这些）
    VISIBLE_CATEGORIES = {'xhr'}

    def __init__(self, output_dir: str, mcp_manager, project_root: str = None):
        """
        Args:
            output_dir: 输出目录（与截图同目录，如 screenshots/<execution_id>/）
            mcp_manager: MCP 管理器，用于获取 playwright 客户端
            project_root: 项目根目录，用于查找 .playwright-mcp/traces
        """
        self.output_dir = Path(output_dir)
        self.mcp_manager = mcp_manager

        # 优先从项目根目录查找 .playwright-mcp/traces
        if project_root:
            self.tracing_base_dir = Path(project_root) / '.playwright-mcp' / 'traces'
        else:
            # 回退到临时目录
            self.tracing_base_dir = Path(tempfile.gettempdir()) / 'playwright-mcp-output'

        self.known_folders: set = set()
        self.known_files: set = set()
        self.step_networks: List[Dict[str, Any]] = []
        self._tracing_active = False
        self._last_trace_time: float = 0  # 记录上一次 trace 的时间戳

    def _get_playwright_client(self):
        """获取 Playwright MCP 客户端"""
        try:
            client = self.mcp_manager.clients.get("playwright")
            if client and client.is_running():
                return client
        except Exception:
            pass
        return None

    def initialize(self):
        """初始化：记录已有 trace 文件夹/文件，启动第一次 tracing"""
        try:
            logger.info(f"[NetworkRecorder] 初始化开始，tracing_base_dir={self.tracing_base_dir}")

            # 初始化 known_files 用于扁平文件结构
            self.known_files = set()

            if self.tracing_base_dir.exists():
                # 记录已有的数字命名文件夹
                self.known_folders = set(
                    d for d in os.listdir(self.tracing_base_dir)
                    if (self.tracing_base_dir / d).is_dir() and d.isdigit()
                )
                logger.info(f"[NetworkRecorder] 发现已存在的文件夹：{self.known_folders}")

                # 记录已有的.network 文件（扁平结构），只记录文件名不记录完整路径
                for f in self.tracing_base_dir.glob('trace-*.network'):
                    self.known_files.add(f.name)
                    mtime = f.stat().st_mtime
                    if mtime > self._last_trace_time:
                        self._last_trace_time = mtime
                logger.info(f"[NetworkRecorder] 发现已存在的.network 文件：{self.known_files}, _last_trace_time={self._last_trace_time}")
            else:
                logger.warning(f"[NetworkRecorder] tracing_base_dir 不存在：{self.tracing_base_dir}")
                self.known_folders = set()

            self.start_tracing()
            logger.info(f"[NetworkRecorder] 初始化完成")
        except Exception as e:
            logger.error(f"[NetworkRecorder] 初始化失败：{e}")
            import traceback
            logger.error(traceback.format_exc())

    def start_tracing(self):
        """启动 tracing"""
        try:
            logger.debug(f"[NetworkRecorder] start_tracing 开始")
            client = self._get_playwright_client()
            if client:
                logger.debug(f"[NetworkRecorder] 获取到 Playwright 客户端，is_running={client.is_running()}")
                # 检查工具是否可用
                tools = client.get_tools()
                tool_names = [t.get('name', '') for t in tools]
                logger.info(f"[NetworkRecorder] Playwright MCP 可用工具：{tool_names}")

                if 'browser_start_tracing' not in tool_names:
                    logger.warning("[NetworkRecorder] browser_start_tracing 工具不可用，跳过 tracing")
                    return

                result = client.call_tool("browser_start_tracing", {})
                logger.info(f"[NetworkRecorder] browser_start_tracing 调用结果：{result}")
                self._tracing_active = True
                logger.info(f"[NetworkRecorder] tracing 已启动")
            else:
                logger.warning("[NetworkRecorder] 无法获取 Playwright 客户端")
        except Exception as e:
            logger.error(f"[NetworkRecorder] start_tracing 失败：{e}")
            import traceback
            logger.error(traceback.format_exc())
            self._tracing_active = False

    def stop_tracing(self):
        """停止 tracing"""
        try:
            logger.debug(f"[NetworkRecorder] stop_tracing 开始，_tracing_active={self._tracing_active}")
            client = self._get_playwright_client()
            if client and self._tracing_active:
                tools = client.get_tools()
                tool_names = [t.get('name', '') for t in tools]
                if 'browser_stop_tracing' not in tool_names:
                    logger.warning("[NetworkRecorder] browser_stop_tracing 工具不可用")
                    return
                result = client.call_tool("browser_stop_tracing", {})
                logger.info(f"[NetworkRecorder] browser_stop_tracing 调用结果：{result}")
                self._tracing_active = False
                logger.info(f"[NetworkRecorder] tracing 已停止")
        except Exception as e:
            logger.error(f"[NetworkRecorder] stop_tracing 失败：{e}")
            import traceback
            logger.error(traceback.format_exc())
            self._tracing_active = False

    def collect_and_restart(self, step_num: int, step_name: str = ""):
        """收集当前步骤的网络数据，然后重新启动 tracing"""
        logger.info(f"[NetworkRecorder] collect_and_restart 开始：step_num={step_num}, step_name={step_name}")
        try:
            self.stop_tracing()
            network_data = self._parse_latest_trace(step_num, step_name)
            if network_data:
                logger.info(f"[NetworkRecorder] 步骤 {step_num} 收集到 {network_data.get('total_requests', 0)} 个请求")
                self.step_networks.append(network_data)
            else:
                logger.warning(f"[NetworkRecorder] 步骤 {step_num} 未收集到网络数据")
            self.start_tracing()
            logger.info(f"[NetworkRecorder] collect_and_restart 完成：step_num={step_num}")
        except Exception as e:
            logger.error(f"[NetworkRecorder] collect_and_restart 失败（步骤 {step_num}）：{e}")
            import traceback
            logger.error(traceback.format_exc())
            try:
                self.start_tracing()
            except Exception:
                pass

    def collect_final(self, step_num: int, step_name: str = ""):
        """收集最后一个步骤的网络数据（不再重新启动）"""
        logger.info(f"[NetworkRecorder] collect_final 开始：step_num={step_num}, step_name={step_name}")
        try:
            self.stop_tracing()
            network_data = self._parse_latest_trace(step_num, step_name)
            if network_data:
                logger.info(f"[NetworkRecorder] 最后步骤收集到 {network_data.get('total_requests', 0)} 个请求")
                self.step_networks.append(network_data)
            else:
                logger.warning(f"[NetworkRecorder] 最后步骤未收集到网络数据")
            logger.info(f"[NetworkRecorder] collect_final 完成")
        except Exception as e:
            logger.error(f"[NetworkRecorder] collect_final 失败（步骤 {step_num}）：{e}")
            import traceback
            logger.error(traceback.format_exc())

    def _parse_latest_trace(self, step_num: int, step_name: str) -> Optional[Dict[str, Any]]:
        """解析最新的 trace 文件（支持扁平文件结构和文件夹结构）"""
        try:
            logger.debug(f"[NetworkRecorder] _parse_latest_trace 开始：step_num={step_num}, tracing_base_dir={self.tracing_base_dir}")

            if not self.tracing_base_dir.exists():
                logger.warning(f"[NetworkRecorder] 步骤 {step_num}：tracing 目录不存在：{self.tracing_base_dir}")
                return None

            # 先尝试查找数字命名的子文件夹（旧逻辑）
            current_folders = set(
                d for d in os.listdir(self.tracing_base_dir)
                if (self.tracing_base_dir / d).is_dir() and d.isdigit()
            )
            new_folders = current_folders - self.known_folders
            logger.debug(f"[NetworkRecorder] 文件夹检查：current={current_folders}, known={self.known_folders}, new={new_folders}")

            if new_folders:
                # 有新增文件夹，使用文件夹逻辑
                latest_folder = max(new_folders, key=lambda d: int(d))
                self.known_folders.add(latest_folder)
                logger.info(f"[NetworkRecorder] 发现新文件夹：{latest_folder}")

                # 查找 .network 文件（可能在 traces 子目录下）
                trace_dir = self.tracing_base_dir / latest_folder
                network_file = trace_dir / 'trace.network'
                if not network_file.exists():
                    traces_dir = trace_dir / 'traces'
                    if traces_dir.exists():
                        network_files = list(traces_dir.glob('*.network'))
                        if network_files:
                            network_file = network_files[0]
                        else:
                            logger.debug(f"[NetworkRecorder] 步骤 {step_num}：traces 目录中未找到.network 文件")
                            return None
                    else:
                        network_files = list(trace_dir.glob('*.network'))
                        if not network_files:
                            logger.debug(f"[NetworkRecorder] 步骤 {step_num}：文件夹中未找到.network 文件")
                            return None
                        network_file = network_files[0]

                logger.info(f"[NetworkRecorder] 使用文件夹结构，network_file={network_file}")
                requests = self._parse_network_file(network_file)
                logger.info(f"[NetworkRecorder] 步骤 {step_num} 解析到 {len(requests)} 个网络请求（文件夹结构）")

                return {
                    "step_num": step_num,
                    "step_name": step_name,
                    "total_requests": len(requests),
                    "requests": requests,
                }

            # 扁平文件结构：直接在根目录查找 .network 文件
            logger.debug(f"[NetworkRecorder] 扁平文件结构检查：known_files={self.known_files}, _last_trace_time={self._last_trace_time}")

            network_files = list(self.tracing_base_dir.glob('trace-*.network'))
            logger.debug(f"[NetworkRecorder] 找到.network 文件：{[f.name for f in network_files]}")

            if not network_files:
                logger.warning(f"[NetworkRecorder] 步骤 {step_num}：扁平目录下未找到.trace.network 文件")
                return None

            # 找到比上一次 trace 时间更晚的文件
            new_network_files = [
                f for f in network_files
                if f.name not in self.known_files and f.stat().st_mtime > self._last_trace_time
            ]
            logger.debug(f"[NetworkRecorder] 新文件检查：new_network_files={[f.name for f in new_network_files]}")

            if not new_network_files:
                # 如果没有新文件，尝试找最新的文件（可能文件写入时时间戳变化不大）
                latest_file = max(network_files, key=lambda f: f.stat().st_mtime)
                if latest_file.name not in self.known_files:
                    new_network_files = [latest_file]
                    logger.debug(f"[NetworkRecorder] 使用最新文件：{latest_file.name}")

            if not new_network_files:
                logger.warning(f"[NetworkRecorder] 步骤 {step_num}：未找到新的.network 文件，所有文件都已在 known_files 中")
                return None

            # 处理最新的文件
            latest_new_file = max(new_network_files, key=lambda f: f.stat().st_mtime)
            self.known_files.add(latest_new_file.name)
            old_last_trace_time = self._last_trace_time
            self._last_trace_time = latest_new_file.stat().st_mtime
            logger.info(f"[NetworkRecorder] 处理新文件：{latest_new_file.name}, mtime={self._last_trace_time}, old_mtime={old_last_trace_time}")

            requests = self._parse_network_file(latest_new_file)
            logger.info(f"[NetworkRecorder] 步骤 {step_num} 解析到 {len(requests)} 个网络请求（扁平结构）")

            return {
                "step_num": step_num,
                "step_name": step_name,
                "total_requests": len(requests),
                "requests": requests,
            }

        except Exception as e:
            logger.error(f"[NetworkRecorder] _parse_latest_trace 失败：{e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def _parse_network_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """解析 .network 文件（JSON Lines 格式）"""
        logger.debug(f"[NetworkRecorder] _parse_network_file 开始：{file_path}")
        requests = []

        # 查找 resources 目录用于读取响应体
        resources_dir = None
        trace_dir = file_path.parent
        if trace_dir.name == 'traces':
            resources_dir = trace_dir.parent / 'resources'
        elif (trace_dir.parent / 'resources').exists():
            resources_dir = trace_dir.parent / 'resources'

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                line_count = 0
                for line in f:
                    line_count += 1
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if entry.get('type') != 'resource-snapshot':
                        continue

                    snapshot = entry.get('snapshot', {})
                    req = snapshot.get('request', {})
                    resp = snapshot.get('response', {})
                    content = snapshot.get('content', {})
                    timings = snapshot.get('timings', {})

                    url = req.get('url', '')
                    method = req.get('method', '')
                    status = resp.get('status', 0)
                    mime_type = content.get('mimeType', '')
                    size = content.get('size', 0)

                    duration = sum(max(0, v) for v in timings.values()) if timings else 0

                    category = self._classify_request(method, mime_type, url)
                    is_filtered = category not in self.VISIBLE_CATEGORIES

                    # 提取请求体和响应体
                    request_headers = {h.get('name', ''): h.get('value', '') for h in req.get('headers', [])}
                    response_headers = {h.get('name', ''): h.get('value', '') for h in resp.get('headers', [])}

                    # 提取请求体（如果有）
                    request_body = req.get('postData', None)

                    # 提取响应体（从 resources 目录读取）
                    response_body = None
                    content_text = content.get('text', None)
                    sha1_ref = content.get('_sha1', None)

                    if content_text:
                        # 直接有 text 字段
                        if mime_type.startswith('text/') or 'json' in mime_type or 'javascript' in mime_type:
                            max_body_size = 10000
                            if len(content_text) <= max_body_size:
                                response_body = content_text
                            else:
                                response_body = content_text[:max_body_size] + '\n... (truncated)'
                    elif sha1_ref and resources_dir:
                        # 从 resources 目录读取
                        resource_path = resources_dir / sha1_ref
                        if resource_path.exists():
                            try:
                                with open(resource_path, 'r', encoding='utf-8') as f:
                                    body_content = f.read()
                                max_body_size = 10000
                                if len(body_content) <= max_body_size:
                                    response_body = body_content
                                else:
                                    response_body = body_content[:max_body_size] + '\n... (truncated)'
                            except Exception as e:
                                logger.debug(f"[NetworkRecorder] 读取响应体失败 {sha1_ref}: {e}")

                    requests.append({
                        "url": url,
                        "short_url": self._shorten_url(url),
                        "method": method,
                        "status": status,
                        "mimeType": mime_type,
                        "category": category,
                        "size": size,
                        "duration": round(duration, 2),
                        "is_filtered": is_filtered,
                        "requestHeaders": request_headers,
                        "responseHeaders": response_headers,
                        "requestBody": request_body,
                        "responseBody": response_body,
                    })
            logger.debug(f"[NetworkRecorder] _parse_network_file 完成：读取 {line_count} 行，解析到 {len(requests)} 个请求")
        except Exception as e:
            logger.error(f"[NetworkRecorder] 解析 .network 文件失败 {file_path}：{e}")
            import traceback
            logger.error(traceback.format_exc())

        return requests

    @classmethod
    def _classify_request(cls, method: str, mime_type: str, url: str) -> str:
        """
        请求分类

        返回：xhr, js, css, image, font, document, media, other
        """
        mime_lower = (mime_type or '').lower()
        method_upper = (method or '').upper()
        url_lower = (url or '').lower()

        # 1. POST/PUT/PATCH/DELETE → XHR
        if method_upper in ('POST', 'PUT', 'PATCH', 'DELETE'):
            return 'xhr'

        # 2. JSON/XML 响应 → XHR
        if 'json' in mime_lower:
            return 'xhr'
        if 'xml' in mime_lower and 'html' not in mime_lower:
            return 'xhr'

        # 3. URL 中的 API 模式 → XHR
        api_patterns = [
            '/api/', '/v1/', '/v2/', '/v3/', '/graphql', '/rest/',
            '/rpc/', '/ws/', '/service/', '/action/',
        ]
        for pattern in api_patterns:
            if pattern in url_lower:
                return 'xhr'

        # 4. JavaScript
        if 'javascript' in mime_lower or 'ecmascript' in mime_lower:
            return 'js'

        # 5. CSS
        if mime_lower == 'text/css':
            return 'css'

        # 6. Image
        if mime_lower.startswith('image/'):
            return 'image'

        # 7. Font
        font_keywords = ('font', 'woff', 'ttf', 'otf', 'eot')
        if any(kw in mime_lower for kw in font_keywords):
            return 'font'

        # 8. Media
        if mime_lower.startswith('video/') or mime_lower.startswith('audio/'):
            return 'media'

        # 9. HTML Document
        if 'html' in mime_lower:
            return 'document'

        # 10. 文件扩展名 fallback
        ext_map = {
            '.js': 'js', '.mjs': 'js',
            '.css': 'css',
            '.png': 'image', '.jpg': 'image', '.jpeg': 'image',
            '.gif': 'image', '.svg': 'image', '.ico': 'image', '.webp': 'image',
            '.woff': 'font', '.woff2': 'font', '.ttf': 'font', '.otf': 'font',
        }
        for ext, cat in ext_map.items():
            if url_lower.endswith(ext):
                return cat

        return 'other'

    @staticmethod
    def _shorten_url(url: str) -> str:
        """缩短 URL 用于前端显示"""
        if not url:
            return ''
        try:
            parsed = urlparse(url)
            path = parsed.path or '/'
            if parsed.query:
                path += '?' + parsed.query[:30] + ('...' if len(parsed.query) > 30 else '')
            display = f"{parsed.netloc}{path}"
            if len(display) > 100:
                display = display[:97] + '...'
            return display
        except Exception:
            if len(url) > 100:
                return url[:97] + '...'
            return url

    def save_results(self) -> Optional[str]:
        """保存所有步骤的网络请求数据到 JSON 文件"""
        logger.info(f"[NetworkRecorder] save_results 开始，共 {len(self.step_networks)} 个步骤")
        try:
            total_requests = sum(s.get('total_requests', 0) for s in self.step_networks)
            total_xhr = sum(
                sum(1 for r in s.get('requests', []) if not r.get('is_filtered', True))
                for s in self.step_networks
            )

            logger.info(f"[NetworkRecorder] 总计：{total_requests} 个请求，{total_xhr} 个 XHR 请求")

            output = {
                "steps": self.step_networks,
                "summary": {
                    "total_steps": len(self.step_networks),
                    "total_requests": total_requests,
                    "total_xhr_requests": total_xhr,
                },
            }

            self.output_dir.mkdir(parents=True, exist_ok=True)
            output_file = self.output_dir / 'network_trace.json'

            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(output, f, ensure_ascii=False, indent=2)

            logger.info(f"[NetworkRecorder] 结果已保存到：{output_file}")
            return str(output_file)

        except Exception as e:
            logger.error(f"[NetworkRecorder] 保存结果失败：{e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
