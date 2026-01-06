"""
CFspider 浏览器模块
基于 Playwright 封装，支持通过 Cloudflare Workers 代理浏览器流量
"""

from urllib.parse import urlparse, parse_qs, unquote
from .vless_client import LocalVlessProxy


def parse_vless_link(vless_link):
    """
    解析 VLESS 链接
    
    支持格式:
        vless://uuid@host:port?type=ws&path=/xxx#name
        vless://uuid@host:port?path=%2Fxxx
        vless://uuid@host:port
    
    Args:
        vless_link: VLESS 链接字符串
        
    Returns:
        dict: 包含 uuid, host, port, path 的字典，解析失败返回 None
    """
    if not vless_link or not vless_link.startswith('vless://'):
        return None
    
    try:
        # 移除 vless:// 前缀
        link = vless_link[8:]
        
        # 分离 fragment（#后面的名称）
        if '#' in link:
            link = link.split('#')[0]
        
        # 分离 query string
        query_str = ""
        if '?' in link:
            link, query_str = link.split('?', 1)
        
        # 解析 uuid@host:port
        if '@' not in link:
            return None
        
        uuid, host_port = link.split('@', 1)
        
        # 解析 host:port
        if ':' in host_port:
            host, port = host_port.rsplit(':', 1)
            port = int(port)
        else:
            host = host_port
            port = 443
        
        # 解析 query 参数
        path = "/"
        if query_str:
            params = parse_qs(query_str)
            if 'path' in params:
                path = unquote(params['path'][0])
        
        return {
            'uuid': uuid,
            'host': host,
            'port': port,
            'path': path
        }
    except Exception:
        return None

try:
    from playwright.sync_api import sync_playwright, Page, Browser as PlaywrightBrowser
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    Page = None
    PlaywrightBrowser = None


class BrowserNotInstalledError(Exception):
    """浏览器未安装错误"""
    pass


class PlaywrightNotInstalledError(Exception):
    """Playwright 未安装错误"""
    pass


class Browser:
    """
    CFspider 浏览器类
    
    封装 Playwright，支持通过 Cloudflare Workers (edgetunnel) 代理浏览器流量
    
    Example:
        >>> import cfspider
        >>> # 通过 edgetunnel Workers 代理
        >>> browser = cfspider.Browser(cf_proxies="wss://v2.kami666.xyz")
        >>> html = browser.html("https://example.com")
        >>> browser.close()
        >>> 
        >>> # 直接使用（无代理）
        >>> browser = cfspider.Browser()
        >>> html = browser.html("https://example.com")
        >>> browser.close()
    """
    
    def __init__(self, cf_proxies=None, headless=True, timeout=30, vless_uuid=None):
        """
        初始化浏览器
        
        Args:
            cf_proxies: 代理地址（选填），支持以下格式：
                        - VLESS 链接: "vless://uuid@host:port?path=/xxx#name"（推荐）
                        - HTTP 代理: "http://ip:port" 或 "ip:port"
                        - SOCKS5 代理: "socks5://ip:port"
                        - edgetunnel 域名: "v2.example.com"（需配合 vless_uuid）
                        不填则直接使用本地网络
            headless: 是否无头模式，默认 True
            timeout: 请求超时时间（秒），默认 30
            vless_uuid: VLESS UUID（选填），使用域名方式时需要指定
                        如果使用完整 VLESS 链接，则无需此参数
            
        Examples:
            # 使用完整 VLESS 链接（推荐，无需填写 vless_uuid）
            browser = Browser(cf_proxies="vless://uuid@v2.example.com:443?path=/")
            
            # 使用域名 + UUID（旧方式）
            browser = Browser(cf_proxies="v2.example.com", vless_uuid="your-uuid")
            
            # 使用 HTTP 代理
            browser = Browser(cf_proxies="127.0.0.1:8080")
            
            # 使用 SOCKS5 代理
            browser = Browser(cf_proxies="socks5://127.0.0.1:1080")
        """
        if not PLAYWRIGHT_AVAILABLE:
            raise PlaywrightNotInstalledError(
                "Playwright 未安装，请运行: pip install cfspider[browser]"
            )
        
        self.cf_proxies = cf_proxies
        self.headless = headless
        self.timeout = timeout
        self._vless_proxy = None
        
        # 解析代理地址
        proxy_url = None
        if cf_proxies:
            # 1. 检查是否是 VLESS 链接
            vless_info = parse_vless_link(cf_proxies)
            if vless_info:
                # 使用 VLESS 链接
                ws_url = f"wss://{vless_info['host']}{vless_info['path']}"
                self._vless_proxy = LocalVlessProxy(ws_url, vless_info['uuid'])
                port = self._vless_proxy.start()
                proxy_url = f"http://127.0.0.1:{port}"
            # 2. HTTP/SOCKS5 代理格式
            elif cf_proxies.startswith('http://') or cf_proxies.startswith('https://') or cf_proxies.startswith('socks5://'):
                proxy_url = cf_proxies
            # 3. IP:PORT 格式
            elif ':' in cf_proxies and cf_proxies.replace('.', '').replace(':', '').isdigit():
                proxy_url = f"http://{cf_proxies}"
            # 4. 域名 + UUID（旧方式）
            elif vless_uuid:
                hostname = cf_proxies.replace('https://', '').replace('http://', '').replace('wss://', '').replace('ws://', '').split('/')[0]
                ws_url = f'wss://{hostname}/{vless_uuid}'
                self._vless_proxy = LocalVlessProxy(ws_url, vless_uuid)
                port = self._vless_proxy.start()
                proxy_url = f"http://127.0.0.1:{port}"
            # 5. 默认当作 HTTP 代理
            else:
                proxy_url = f"http://{cf_proxies}"
        
        # 启动 Playwright
        self._playwright = sync_playwright().start()
        
        # 启动浏览器
        launch_options = {"headless": headless}
        if proxy_url:
            launch_options["proxy"] = {"server": proxy_url}
        
        try:
            self._browser = self._playwright.chromium.launch(**launch_options)
        except Exception as e:
            if self._vless_proxy:
                self._vless_proxy.stop()
            self._playwright.stop()
            if "Executable doesn't exist" in str(e):
                raise BrowserNotInstalledError(
                    "Chromium 浏览器未安装，请运行: cfspider install"
                )
            raise
        
        # 创建默认上下文
        self._context = self._browser.new_context(
            ignore_https_errors=True
        )
        self._context.set_default_timeout(timeout * 1000)
    
    def get(self, url):
        """
        打开页面并返回 Page 对象
        
        Args:
            url: 目标 URL
            
        Returns:
            Page: Playwright Page 对象，可用于自动化操作
        """
        page = self._context.new_page()
        page.goto(url, wait_until="networkidle")
        return page
    
    def html(self, url, wait_until="domcontentloaded"):
        """
        获取页面渲染后的 HTML
        
        Args:
            url: 目标 URL
            wait_until: 等待策略，可选 "load", "domcontentloaded", "networkidle"
            
        Returns:
            str: 渲染后的 HTML 内容
        """
        page = self._context.new_page()
        try:
            page.goto(url, wait_until=wait_until)
            return page.content()
        finally:
            page.close()
    
    def screenshot(self, url, path=None, full_page=False):
        """
        页面截图
        
        Args:
            url: 目标 URL
            path: 保存路径，如 "screenshot.png"
            full_page: 是否截取整个页面，默认 False
            
        Returns:
            bytes: 截图的二进制数据
        """
        page = self._context.new_page()
        try:
            page.goto(url, wait_until="networkidle")
            return page.screenshot(path=path, full_page=full_page)
        finally:
            page.close()
    
    def pdf(self, url, path=None):
        """
        生成页面 PDF
        
        Args:
            url: 目标 URL
            path: 保存路径，如 "page.pdf"
            
        Returns:
            bytes: PDF 的二进制数据
            
        Note:
            PDF 生成仅在无头模式下可用
        """
        if not self.headless:
            raise ValueError("PDF 生成仅在无头模式 (headless=True) 下可用")
        
        page = self._context.new_page()
        try:
            page.goto(url, wait_until="networkidle")
            return page.pdf(path=path)
        finally:
            page.close()
    
    def execute_script(self, url, script):
        """
        在页面中执行 JavaScript
        
        Args:
            url: 目标 URL
            script: 要执行的 JavaScript 代码
            
        Returns:
            执行结果
        """
        page = self._context.new_page()
        try:
            page.goto(url, wait_until="networkidle")
            return page.evaluate(script)
        finally:
            page.close()
    
    def new_page(self):
        """
        创建新页面
        
        Returns:
            Page: 新的 Playwright Page 对象
        """
        return self._context.new_page()
    
    def close(self):
        """关闭浏览器和代理"""
        try:
            self._context.close()
        except:
            pass
        
        try:
            self._browser.close()
        except:
            pass
        
        try:
            self._playwright.stop()
        except:
            pass
        
        if self._vless_proxy:
            try:
                self._vless_proxy.stop()
            except:
                pass
    
    def __enter__(self):
        """支持 with 语句"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """支持 with 语句"""
        self.close()
        return False

