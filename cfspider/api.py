"""
CFspider 核心 API 模块

提供同步 HTTP 请求功能，支持：
- 通过 Cloudflare Workers 代理请求
- TLS 指纹模拟 (curl_cffi)
- HTTP/2 支持 (httpx)
- 隐身模式（完整浏览器请求头）
- IP 地图可视化
"""

import requests
import time
from urllib.parse import urlencode, quote
from typing import Optional, Any

# 延迟导入 IP 地图模块
from . import ip_map

# 延迟导入 httpx，仅在需要 HTTP/2 时使用
_httpx = None

def _get_httpx():
    """延迟加载 httpx 模块"""
    global _httpx
    if _httpx is None:
        try:
            import httpx
            _httpx = httpx
        except ImportError:
            raise ImportError(
                "httpx is required for HTTP/2 support. "
                "Install it with: pip install httpx[http2]"
            )
    return _httpx


# 延迟导入 curl_cffi，仅在需要 TLS 指纹时使用
_curl_cffi = None

def _get_curl_cffi():
    """延迟加载 curl_cffi 模块"""
    global _curl_cffi
    if _curl_cffi is None:
        try:
            from curl_cffi import requests as curl_requests
            _curl_cffi = curl_requests
        except ImportError:
            raise ImportError(
                "curl_cffi is required for TLS fingerprint impersonation. "
                "Install it with: pip install curl_cffi"
            )
    return _curl_cffi


class CFSpiderResponse:
    """
    CFspider 响应对象
    
    封装 HTTP 响应，提供与 requests.Response 兼容的接口，
    并额外提供 Cloudflare 特有的信息（如节点代码、Ray ID）。
    
    Attributes:
        cf_colo (str): Cloudflare 数据中心代码（如 NRT=东京, SIN=新加坡, LAX=洛杉矶）
                       使用 Workers 代理时可用，表示请求经过的 CF 节点
        cf_ray (str): Cloudflare Ray ID，每个请求的唯一标识符
                      可用于调试和追踪请求
        text (str): 响应文本内容（自动解码）
        content (bytes): 响应原始字节内容
        status_code (int): HTTP 状态码（如 200, 404, 500）
        headers (dict): 响应头字典
        cookies: 响应 Cookie
        url (str): 最终请求的 URL（跟随重定向后）
        encoding (str): 响应编码
    
    Methods:
        json(**kwargs): 将响应解析为 JSON
        raise_for_status(): 当状态码非 2xx 时抛出 HTTPError
    
    Example:
        >>> response = cfspider.get("https://httpbin.org/ip", cf_proxies="...")
        >>> print(response.status_code)  # 200
        >>> print(response.cf_colo)      # NRT (东京节点)
        >>> print(response.cf_ray)       # 8a1b2c3d4e5f-NRT
        >>> data = response.json()
        >>> print(data['origin'])        # Cloudflare IP
    """
    
    def __init__(self, response, cf_colo=None, cf_ray=None):
        """
        初始化响应对象
        
        Args:
            response: 原始 requests/httpx/curl_cffi 响应对象
            cf_colo: Cloudflare 数据中心代码（从响应头获取）
            cf_ray: Cloudflare Ray ID（从响应头获取）
        """
        self._response = response
        self.cf_colo = cf_colo
        self.cf_ray = cf_ray
    
    @property
    def text(self) -> str:
        """响应文本内容（自动解码）"""
        return self._response.text
    
    @property
    def content(self) -> bytes:
        """响应原始字节内容"""
        return self._response.content
    
    @property
    def status_code(self) -> int:
        """HTTP 状态码"""
        return self._response.status_code
    
    @property
    def headers(self):
        """响应头字典"""
        return self._response.headers
    
    @property
    def cookies(self):
        """响应 Cookie"""
        return self._response.cookies
    
    @property
    def url(self) -> str:
        """最终请求的 URL（跟随重定向后）"""
        return self._response.url
    
    @property
    def encoding(self) -> Optional[str]:
        """响应编码"""
        return self._response.encoding
    
    @encoding.setter
    def encoding(self, value: str):
        """设置响应编码"""
        self._response.encoding = value
    
    def json(self, **kwargs) -> Any:
        """
        将响应解析为 JSON
        
        Args:
            **kwargs: 传递给 json.loads() 的参数
            
        Returns:
            解析后的 JSON 数据（dict 或 list）
            
        Raises:
            JSONDecodeError: 当响应不是有效的 JSON 时
        """
        return self._response.json(**kwargs)
    
    def raise_for_status(self):
        """
        当状态码非 2xx 时抛出 HTTPError
        
        Raises:
            requests.HTTPError: 当状态码表示错误时
        """
        self._response.raise_for_status()
    
    # ========== 数据提取方法 ==========
    
    def _get_extractor(self):
        """获取数据提取器（延迟初始化）"""
        if not hasattr(self, '_extractor') or self._extractor is None:
            from .extract import Extractor
            content_type = "json" if self._is_json_response() else "html"
            self._extractor = Extractor(self.text, content_type)
        return self._extractor
    
    def _is_json_response(self) -> bool:
        """判断是否是 JSON 响应"""
        content_type = self.headers.get("content-type", "")
        return "application/json" in content_type.lower()
    
    def find(self, selector: str, attr: str = None, strip: bool = True, 
             regex: str = None, parser=None):
        """
        查找第一个匹配的元素（最简单的 API）
        
        自动识别选择器类型：
        - 以 $ 开头：JSONPath
        - 以 // 开头：XPath
        - 其他：CSS 选择器
        
        Args:
            selector: 选择器（CSS/XPath/JSONPath）
            attr: 要提取的属性名
            strip: 是否去除空白
            regex: 正则表达式提取
            parser: 自定义解析函数
            
        Returns:
            匹配的文本或属性值
            
        Example:
            >>> response.find("h1")          # CSS
            >>> response.find("//h1/text()") # XPath
            >>> response.find("$.title")     # JSONPath
        """
        return self._get_extractor().find(selector, attr=attr, strip=strip, 
                                          regex=regex, parser=parser)
    
    def find_all(self, selector: str, attr: str = None, strip: bool = True):
        """
        查找所有匹配的元素
        
        Args:
            selector: 选择器（CSS/XPath/JSONPath）
            attr: 要提取的属性名
            strip: 是否去除空白
            
        Returns:
            匹配的文本或属性值列表
        """
        return self._get_extractor().find_all(selector, attr=attr, strip=strip)
    
    def css(self, selector: str, attr: str = None, html: bool = False, strip: bool = True):
        """
        使用 CSS 选择器提取第一个匹配元素
        
        Args:
            selector: CSS 选择器
            attr: 要提取的属性名
            html: 是否返回 HTML 而非文本
            strip: 是否去除空白
            
        Returns:
            匹配元素的文本、属性或 HTML
        """
        return self._get_extractor().css(selector, attr=attr, html=html, strip=strip)
    
    def css_all(self, selector: str, attr: str = None, html: bool = False, strip: bool = True):
        """
        使用 CSS 选择器提取所有匹配元素
        
        Args:
            selector: CSS 选择器
            attr: 要提取的属性名
            html: 是否返回 HTML 而非文本
            strip: 是否去除空白
            
        Returns:
            匹配元素的文本、属性或 HTML 列表
        """
        return self._get_extractor().css_all(selector, attr=attr, html=html, strip=strip)
    
    def css_one(self, selector: str):
        """
        返回第一个匹配的 Element 对象，支持链式操作
        
        Args:
            selector: CSS 选择器
            
        Returns:
            Element 对象
        """
        return self._get_extractor().css_one(selector)
    
    def xpath(self, expression: str):
        """
        使用 XPath 表达式提取第一个匹配
        
        Args:
            expression: XPath 表达式
            
        Returns:
            匹配的文本或属性值
        """
        return self._get_extractor().xpath(expression)
    
    def xpath_all(self, expression: str):
        """
        使用 XPath 表达式提取所有匹配
        
        Args:
            expression: XPath 表达式
            
        Returns:
            匹配的文本或属性值列表
        """
        return self._get_extractor().xpath_all(expression)
    
    def xpath_one(self, expression: str):
        """
        返回第一个匹配的 Element 对象
        
        Args:
            expression: XPath 表达式
            
        Returns:
            Element 对象
        """
        return self._get_extractor().xpath_one(expression)
    
    def jpath(self, expression: str):
        """
        使用 JSONPath 表达式提取第一个匹配
        
        Args:
            expression: JSONPath 表达式（如 $.data.items[0].name）
            
        Returns:
            匹配的值
        """
        return self._get_extractor().jpath(expression)
    
    def jpath_all(self, expression: str):
        """
        使用 JSONPath 表达式提取所有匹配
        
        Args:
            expression: JSONPath 表达式
            
        Returns:
            匹配的值列表
        """
        return self._get_extractor().jpath_all(expression)
    
    def pick(self, **fields):
        """
        批量提取多个字段
        
        Args:
            **fields: 字段名=选择器 的映射
                - 字符串：CSS 选择器，提取文本
                - 元组 (selector, attr)：提取属性
                - 元组 (selector, attr, converter)：提取并转换
                
        Returns:
            ExtractResult 字典，支持直接保存
            
        Example:
            >>> data = response.pick(
            ...     title="h1",
            ...     links=("a", "href"),
            ...     price=(".price", "text", float),
            ... )
            >>> data.save("output.csv")
        """
        result = self._get_extractor().pick(**fields)
        result.url = str(self.url)
        return result
    
    def extract(self, rules: dict):
        """
        使用规则字典提取数据（支持前缀指定类型）
        
        Args:
            rules: 字段名到选择器的映射
                选择器可以带前缀指定类型：
                - "css:h1.title" 或直接 "h1.title"
                - "xpath://a/@href"
                - "jsonpath:$.data.name"
                
        Returns:
            ExtractResult 字典
        """
        result = self._get_extractor().extract(rules)
        result.url = str(self.url)
        return result
    
    def save(self, filepath: str, encoding: str = "utf-8"):
        """
        保存响应内容到文件
        
        Args:
            filepath: 输出文件路径
            encoding: 文件编码（仅用于文本内容）
            
        Returns:
            输出文件的绝对路径
        """
        from .export import save_response
        return save_response(self.content, filepath, encoding=encoding)


def request(method, url, cf_proxies=None, cf_workers=True, http2=False, impersonate=None, 
             map_output=False, map_file="cfspider_map.html", 
             stealth=False, stealth_browser='chrome', delay=None, token=None, **kwargs):
    """
    发送 HTTP 请求 / Send HTTP request
    
    这是 CFspider 的核心函数，支持多种代理模式和反爬虫功能。
    This is the core function of CFspider, supporting multiple proxy modes and anti-crawler features.
    
    Args:
        method (str): HTTP 方法（GET, POST, PUT, DELETE, HEAD, OPTIONS, PATCH）
                     / HTTP method (GET, POST, PUT, DELETE, HEAD, OPTIONS, PATCH)
        url (str): 目标 URL，必须包含协议（https://）
                  / Target URL (must include protocol, e.g., https://)
        cf_proxies (str, optional): 代理地址，根据 cf_workers 参数有不同含义
                                   / Proxy address, meaning depends on cf_workers parameter
            - 当 cf_workers=True 时：填写 CFspider Workers 地址（如 "https://your-workers.dev"）
            - When cf_workers=True: CFspider Workers address (e.g., "https://your-workers.dev")
            - 当 cf_workers=False 时：填写普通 HTTP/SOCKS5 代理（如 "http://127.0.0.1:8080"）
            - When cf_workers=False: Regular HTTP/SOCKS5 proxy (e.g., "http://127.0.0.1:8080")
            - 不填写时：直接请求目标 URL，不使用代理
            - None: Direct request without proxy
        cf_workers (bool): 是否使用 CFspider Workers API（默认 True）
                          / Whether to use CFspider Workers API (default: True)
            - True: cf_proxies 是 Workers 地址，请求通过 Workers API 转发
            - True: cf_proxies is Workers address, requests forwarded via Workers API
            - False: cf_proxies 是普通代理，使用 requests/httpx 的 proxies 参数
            - False: cf_proxies is regular proxy, uses requests/httpx proxies parameter
        http2 (bool): 是否启用 HTTP/2 协议（默认 False）
                     / Whether to enable HTTP/2 protocol (default: False)
            - True: 使用 httpx 客户端，支持 HTTP/2
            - True: Uses httpx client with HTTP/2 support
            - False: 使用 requests 库（默认行为）
            - False: Uses requests library (default behavior)
            - 注意：http2 和 impersonate 不能同时使用
            - Note: http2 and impersonate cannot be used together
        impersonate (str, optional): TLS 指纹模拟，模拟真实浏览器的 TLS 握手特征
                                   / TLS fingerprint impersonation, mimics real browser TLS handshake
            - 可选值：chrome131, chrome124, safari18_0, firefox133, edge101 等
            - Options: chrome131, chrome124, safari18_0, firefox133, edge101, etc.
            - 设置后自动使用 curl_cffi 发送请求
            - Automatically uses curl_cffi when set
            - 完整列表：cfspider.get_supported_browsers()
            - Full list: cfspider.get_supported_browsers()
        map_output (bool): 是否生成 IP 地图 HTML 文件（默认 False）
                          / Whether to generate IP map HTML file (default: False)
            - True: 请求完成后生成包含代理 IP 信息的交互式地图
            - True: Generates interactive map with proxy IP information after request
        map_file (str): 地图输出文件名（默认 "cfspider_map.html"）
                       / Map output filename (default: "cfspider_map.html")
        stealth (bool): 是否启用隐身模式（默认 False）
                       / Whether to enable stealth mode (default: False)
            - True: 自动添加 15+ 个完整浏览器请求头，模拟真实浏览器访问
            - True: Automatically adds 15+ complete browser headers, mimics real browser
            - 添加的请求头包括：User-Agent, Accept, Accept-Language, Sec-Fetch-*, Sec-CH-UA 等
            - Headers include: User-Agent, Accept, Accept-Language, Sec-Fetch-*, Sec-CH-UA, etc.
        stealth_browser (str): 隐身模式使用的浏览器类型（默认 'chrome'）
                              / Stealth mode browser type (default: 'chrome')
            - 可选值：chrome, firefox, safari, edge, chrome_mobile
            - Options: chrome, firefox, safari, edge, chrome_mobile
        delay (tuple, optional): 请求前的随机延迟范围（秒）
                                / Random delay range before request (seconds)
            - 如 (1, 3) 表示请求前随机等待 1-3 秒
            - e.g., (1, 3) means random wait 1-3 seconds before request
            - 用于模拟人类行为，避免被反爬系统检测
            - Used to simulate human behavior, avoid anti-crawler detection
        token (str, optional): Workers API 鉴权 token
                               / Workers API authentication token
            - 当使用 Workers API（cf_workers=True）时，将 token 添加到查询参数
            - When using Workers API (cf_workers=True), adds token to query parameters
            - 如果 Workers 端配置了 TOKEN 环境变量，必须提供有效的 token
            - Required when Workers has TOKEN environment variable configured
            - 格式：从查询参数 ?token=xxx 传递
            - Format: Passed via query parameter ?token=xxx
        **kwargs: 其他参数，与 requests 库完全兼容
                 / Other parameters, fully compatible with requests library
            - params (dict): URL 查询参数 / URL query parameters
            - headers (dict): 自定义请求头（会与隐身模式头合并）
                            / Custom headers (merged with stealth mode headers)
            - data (dict/str): 表单数据 / Form data
            - json (dict): JSON 数据（自动设置 Content-Type）
                          / JSON data (Content-Type set automatically)
            - cookies (dict): Cookie
            - timeout (int/float): 超时时间（秒），默认 30
                                  / Timeout (seconds), default: 30
            - allow_redirects (bool): 是否跟随重定向，默认 True
                                    / Whether to follow redirects, default: True
            - verify (bool): 是否验证 SSL 证书，默认 True
                           / Whether to verify SSL certificate, default: True
    
    Returns:
        CFSpiderResponse: 响应对象，包含以下属性
                         / Response object with the following attributes
            - text: 响应文本 / Response text
            - content: 响应字节 / Response bytes
            - json(): 解析 JSON / Parse JSON
            - status_code: HTTP 状态码 / HTTP status code
            - headers: 响应头 / Response headers
            - cf_colo: Cloudflare 节点代码（使用 Workers 时可用）
                      / Cloudflare colo code (available when using Workers)
            - cf_ray: Cloudflare Ray ID
    
    Raises:
        ImportError: 当需要的可选依赖未安装时
                    / When required optional dependencies are not installed
            - http2=True 需要 httpx[http2] / http2=True requires httpx[http2]
            - impersonate 需要 curl_cffi / impersonate requires curl_cffi
        ValueError: 当 http2 和 impersonate 同时启用时
                   / When http2 and impersonate are both enabled
        requests.RequestException: 网络请求失败时
                                   / When network request fails
    
    Examples:
        >>> import cfspider
        >>> 
        >>> # 基本 GET 请求
        >>> response = cfspider.get("https://httpbin.org/ip")
        >>> print(response.json())
        >>> 
        >>> # 使用 Workers 代理
        >>> response = cfspider.get(
        ...     "https://httpbin.org/ip",
        ...     cf_proxies="https://your-workers.dev"
        ... )
        >>> print(response.cf_colo)  # NRT, SIN, LAX 等
        >>> 
        >>> # 隐身模式 + TLS 指纹
        >>> response = cfspider.get(
        ...     "https://example.com",
        ...     stealth=True,
        ...     impersonate="chrome131"
        ... )
    
    Notes:
        - http2 和 impersonate 使用不同的后端（httpx/curl_cffi），不能同时启用
        - 隐身模式的请求头优先级：用户自定义 > stealth 默认头
        - 使用 Workers 代理时，自定义请求头通过 X-CFSpider-Header-* 传递
    """
    # 应用随机延迟
    if delay:
        from .stealth import random_delay
        random_delay(delay[0], delay[1])
    
    params = kwargs.pop("params", None)
    headers = kwargs.pop("headers", {})
    
    # 如果启用隐身模式，添加完整的浏览器请求头
    if stealth:
        from .stealth import get_stealth_headers
        stealth_headers = get_stealth_headers(stealth_browser)
        # 用户自定义的 headers 优先级更高
        final_headers = stealth_headers.copy()
        final_headers.update(headers)
        headers = final_headers
    data = kwargs.pop("data", None)
    json_data = kwargs.pop("json", None)
    cookies = kwargs.pop("cookies", None)
    timeout = kwargs.pop("timeout", 30)
    
    # 记录请求开始时间
    start_time = time.time()
    
    # 如果指定了 impersonate，使用 curl_cffi
    if impersonate:
        response = _request_impersonate(
            method, url, cf_proxies, cf_workers, impersonate,
            params=params, headers=headers, data=data,
            json_data=json_data, cookies=cookies, timeout=timeout,
            token=token, **kwargs
        )
        _handle_map_output(response, url, start_time, map_output, map_file)
        return response
    
    # 如果启用 HTTP/2，使用 httpx
    if http2:
        response = _request_httpx(
            method, url, cf_proxies, cf_workers,
            params=params, headers=headers, data=data,
            json_data=json_data, cookies=cookies, timeout=timeout,
            token=token, **kwargs
        )
        _handle_map_output(response, url, start_time, map_output, map_file)
        return response
    
    # 如果没有指定 cf_proxies，直接使用 requests
    if not cf_proxies:
        resp = requests.request(
            method,
            url,
            params=params,
            headers=headers,
            data=data,
            json=json_data,
            cookies=cookies,
            timeout=timeout,
            **kwargs
        )
        response = CFSpiderResponse(resp)
        _handle_map_output(response, url, start_time, map_output, map_file)
        return response
    
    # cf_workers=False：使用普通代理
    if not cf_workers:
        # 处理代理格式
        proxy_url = cf_proxies
        if not proxy_url.startswith(('http://', 'https://', 'socks5://')):
            proxy_url = f"http://{proxy_url}"
        
        proxies = {
            "http": proxy_url,
            "https": proxy_url
        }
        
        resp = requests.request(
            method,
            url,
            params=params,
            headers=headers,
            data=data,
            json=json_data,
            cookies=cookies,
            timeout=timeout,
            proxies=proxies,
            **kwargs
        )
        response = CFSpiderResponse(resp)
        _handle_map_output(response, url, start_time, map_output, map_file)
        return response
    
    # cf_workers=True：使用 CFspider Workers API 代理
    cf_proxies_url = cf_proxies.rstrip("/")
    
    # 确保有协议前缀
    if not cf_proxies_url.startswith(('http://', 'https://')):
        cf_proxies_url = f"https://{cf_proxies_url}"
    
    target_url = url
    if params:
        target_url = f"{url}?{urlencode(params)}"
    
    # 构建代理 URL，添加 token 参数（如果提供）
    proxy_url = f"{cf_proxies_url}/proxy?url={quote(target_url, safe='')}&method={method.upper()}"
    if token:
        proxy_url += f"&token={quote(token, safe='')}"
    
    request_headers = {}
    if headers:
        for key, value in headers.items():
            request_headers[f"X-CFSpider-Header-{key}"] = value
    
    if cookies:
        cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
        request_headers["X-CFSpider-Header-Cookie"] = cookie_str
    
    resp = requests.post(
        proxy_url,
        headers=request_headers,
        data=data,
        json=json_data,
        timeout=timeout,
        **kwargs
    )
    
    cf_colo = resp.headers.get("X-CF-Colo")
    cf_ray = resp.headers.get("CF-Ray")
    
    response = CFSpiderResponse(resp, cf_colo=cf_colo, cf_ray=cf_ray)
    _handle_map_output(response, url, start_time, map_output, map_file)
    return response


def _handle_map_output(response, url, start_time, map_output, map_file):
    """处理 IP 地图输出"""
    if not map_output:
        return
    
    # 计算响应时间
    response_time = (time.time() - start_time) * 1000  # 毫秒
    
    # 收集 IP 记录
    ip_map.add_ip_record(
        url=url,
        ip=None,  # 无法直接获取 IP，但有 cf_colo
        cf_colo=getattr(response, 'cf_colo', None),
        cf_ray=getattr(response, 'cf_ray', None),
        status_code=response.status_code,
        response_time=response_time
    )
    
    # 生成地图 HTML
    ip_map.generate_map_html(output_file=map_file)


def _request_impersonate(method, url, cf_proxies, cf_workers, impersonate,
                         params=None, headers=None, data=None, json_data=None,
                         cookies=None, timeout=30, token=None, **kwargs):
    """使用 curl_cffi 发送请求（支持 TLS 指纹模拟）"""
    curl_requests = _get_curl_cffi()
    
    # 如果没有指定 cf_proxies，直接请求
    if not cf_proxies:
        response = curl_requests.request(
            method,
            url,
            params=params,
            headers=headers,
            data=data,
            json=json_data,
            cookies=cookies,
            timeout=timeout,
            impersonate=impersonate,
            **kwargs
        )
        return CFSpiderResponse(response)
    
    # cf_workers=False：使用普通代理
    if not cf_workers:
        proxy_url = cf_proxies
        if not proxy_url.startswith(('http://', 'https://', 'socks5://')):
            proxy_url = f"http://{proxy_url}"
        
        response = curl_requests.request(
            method,
            url,
            params=params,
            headers=headers,
            data=data,
            json=json_data,
            cookies=cookies,
            timeout=timeout,
            impersonate=impersonate,
            proxies={"http": proxy_url, "https": proxy_url},
            **kwargs
        )
        return CFSpiderResponse(response)
    
    # cf_workers=True：使用 CFspider Workers API 代理
    cf_proxies = cf_proxies.rstrip("/")
    
    if not cf_proxies.startswith(('http://', 'https://')):
        cf_proxies = f"https://{cf_proxies}"
    
    target_url = url
    if params:
        target_url = f"{url}?{urlencode(params)}"
    
    proxy_url = f"{cf_proxies}/proxy?url={quote(target_url, safe='')}&method={method.upper()}"
    if token:
        proxy_url += f"&token={quote(token, safe='')}"
    
    request_headers = {}
    if headers:
        for key, value in headers.items():
            request_headers[f"X-CFSpider-Header-{key}"] = value
    
    if cookies:
        cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
        request_headers["X-CFSpider-Header-Cookie"] = cookie_str
    
    response = curl_requests.post(
        proxy_url,
        headers=request_headers,
        data=data,
        json=json_data,
        timeout=timeout,
        impersonate=impersonate,
        **kwargs
    )
    
    cf_colo = response.headers.get("X-CF-Colo")
    cf_ray = response.headers.get("CF-Ray")
    
    return CFSpiderResponse(response, cf_colo=cf_colo, cf_ray=cf_ray)


def _request_httpx(method, url, cf_proxies, cf_workers, params=None, headers=None,
                   data=None, json_data=None, cookies=None, timeout=30, token=None, **kwargs):
    """使用 httpx 发送请求（支持 HTTP/2）"""
    httpx = _get_httpx()
    
    # 如果没有指定 cf_proxies，直接请求
    if not cf_proxies:
        with httpx.Client(http2=True, timeout=timeout) as client:
            response = client.request(
                method,
                url,
                params=params,
                headers=headers,
                data=data,
                json=json_data,
                cookies=cookies,
                **kwargs
            )
            return CFSpiderResponse(response)
    
    # cf_workers=False：使用普通代理
    if not cf_workers:
        proxy_url = cf_proxies
        if not proxy_url.startswith(('http://', 'https://', 'socks5://')):
            proxy_url = f"http://{proxy_url}"
        
        with httpx.Client(http2=True, timeout=timeout, proxy=proxy_url) as client:
            response = client.request(
                method,
                url,
                params=params,
                headers=headers,
                data=data,
                json=json_data,
                cookies=cookies,
                **kwargs
            )
            return CFSpiderResponse(response)
    
    # cf_workers=True：使用 CFspider Workers API 代理
    cf_proxies = cf_proxies.rstrip("/")
    
    if not cf_proxies.startswith(('http://', 'https://')):
        cf_proxies = f"https://{cf_proxies}"
    
    target_url = url
    if params:
        target_url = f"{url}?{urlencode(params)}"
    
    proxy_url = f"{cf_proxies}/proxy?url={quote(target_url, safe='')}&method={method.upper()}"
    if token:
        proxy_url += f"&token={quote(token, safe='')}"
    
    request_headers = {}
    if headers:
        for key, value in headers.items():
            request_headers[f"X-CFSpider-Header-{key}"] = value
    
    if cookies:
        cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
        request_headers["X-CFSpider-Header-Cookie"] = cookie_str
    
    with httpx.Client(http2=True, timeout=timeout) as client:
        response = client.post(
            proxy_url,
            headers=request_headers,
            data=data,
            json=json_data,
            **kwargs
        )
    
    cf_colo = response.headers.get("X-CF-Colo")
    cf_ray = response.headers.get("CF-Ray")
    
    return CFSpiderResponse(response, cf_colo=cf_colo, cf_ray=cf_ray)


def get(url, cf_proxies=None, cf_workers=True, http2=False, impersonate=None,
        map_output=False, map_file="cfspider_map.html",
        stealth=False, stealth_browser='chrome', delay=None, token=None, **kwargs):
    """
    发送 GET 请求 / Send GET request
    
    Args:
        url (str): 目标 URL / Target URL (must include protocol, e.g., https://)
        cf_proxies (str, optional): 代理地址 / Proxy address
            - 当 cf_workers=True 时：CFspider Workers 地址（如 "https://your-workers.dev"）
            - When cf_workers=True: CFspider Workers address (e.g., "https://your-workers.dev")
            - 当 cf_workers=False 时：普通 HTTP/SOCKS5 代理（如 "http://127.0.0.1:8080"）
            - When cf_workers=False: Regular HTTP/SOCKS5 proxy (e.g., "http://127.0.0.1:8080")
            - 不填写时：直接请求，不使用代理 / None: Direct request without proxy
        cf_workers (bool): 是否使用 CFspider Workers API（默认 True）
                          / Whether to use CFspider Workers API (default: True)
        http2 (bool): 是否启用 HTTP/2 协议（默认 False）
                     / Whether to enable HTTP/2 protocol (default: False)
        impersonate (str, optional): TLS 指纹模拟 / TLS fingerprint impersonation
            - 可选值：chrome131, chrome124, safari18_0, firefox133, edge101 等
            - Options: chrome131, chrome124, safari18_0, firefox133, edge101, etc.
            - 设置后自动使用 curl_cffi 发送请求
            - Automatically uses curl_cffi when set
        map_output (bool): 是否生成 IP 地图 HTML 文件（默认 False）
                          / Whether to generate IP map HTML file (default: False)
        map_file (str): 地图输出文件名（默认 "cfspider_map.html"）
                       / Map output filename (default: "cfspider_map.html")
        stealth (bool): 是否启用隐身模式（默认 False）
                       / Whether to enable stealth mode (default: False)
            - True: 自动添加 15+ 个完整浏览器请求头
            - True: Automatically adds 15+ complete browser headers
        stealth_browser (str): 隐身模式浏览器类型（默认 'chrome'）
                              / Stealth mode browser type (default: 'chrome')
            - 可选值：chrome, firefox, safari, edge, chrome_mobile
            - Options: chrome, firefox, safari, edge, chrome_mobile
        delay (tuple, optional): 请求前随机延迟范围（秒），如 (1, 3)
                                / Random delay range before request (seconds), e.g., (1, 3)
        token (str, optional): Workers API 鉴权 token
                               / Workers API authentication token
            - 当 Workers 配置了 TOKEN 环境变量时必填
            - Required when Workers has TOKEN environment variable configured
        **kwargs: 其他参数，与 requests 库完全兼容
                 / Other parameters, fully compatible with requests library
            - params (dict): URL 查询参数 / URL query parameters
            - headers (dict): 自定义请求头 / Custom headers
            - data (dict/str): 表单数据 / Form data
            - json (dict): JSON 数据 / JSON data
            - cookies (dict): Cookie
            - timeout (int/float): 超时时间（秒），默认 30 / Timeout (seconds), default: 30
    
    Returns:
        CFSpiderResponse: 响应对象 / Response object
            - text: 响应文本 / Response text
            - content: 响应字节 / Response bytes
            - json(): 解析 JSON / Parse JSON
            - status_code: HTTP 状态码 / HTTP status code
            - headers: 响应头 / Response headers
            - cf_colo: Cloudflare 节点代码（使用 Workers 时可用）
                      / Cloudflare colo code (available when using Workers)
            - cf_ray: Cloudflare Ray ID
    """
    return request("GET", url, cf_proxies=cf_proxies, cf_workers=cf_workers, 
                   http2=http2, impersonate=impersonate,
                   map_output=map_output, map_file=map_file,
                   stealth=stealth, stealth_browser=stealth_browser, delay=delay, token=token, **kwargs)


def post(url, cf_proxies=None, cf_workers=True, http2=False, impersonate=None,
         map_output=False, map_file="cfspider_map.html",
         stealth=False, stealth_browser='chrome', delay=None, token=None, **kwargs):
    """
    发送 POST 请求 / Send POST request
    
    Args:
        url (str): 目标 URL / Target URL (must include protocol, e.g., https://)
        cf_proxies (str, optional): 代理地址 / Proxy address
            - 当 cf_workers=True 时：CFspider Workers 地址（如 "https://your-workers.dev"）
            - When cf_workers=True: CFspider Workers address (e.g., "https://your-workers.dev")
            - 当 cf_workers=False 时：普通 HTTP/SOCKS5 代理（如 "http://127.0.0.1:8080"）
            - When cf_workers=False: Regular HTTP/SOCKS5 proxy (e.g., "http://127.0.0.1:8080")
            - 不填写时：直接请求，不使用代理 / None: Direct request without proxy
        cf_workers (bool): 是否使用 CFspider Workers API（默认 True）
                          / Whether to use CFspider Workers API (default: True)
        http2 (bool): 是否启用 HTTP/2 协议（默认 False）
                     / Whether to enable HTTP/2 protocol (default: False)
        impersonate (str, optional): TLS 指纹模拟 / TLS fingerprint impersonation
            - 可选值：chrome131, chrome124, safari18_0, firefox133, edge101 等
            - Options: chrome131, chrome124, safari18_0, firefox133, edge101, etc.
        map_output (bool): 是否生成 IP 地图 HTML 文件（默认 False）
                          / Whether to generate IP map HTML file (default: False)
        map_file (str): 地图输出文件名（默认 "cfspider_map.html"）
                       / Map output filename (default: "cfspider_map.html")
        stealth (bool): 是否启用隐身模式（默认 False）
                       / Whether to enable stealth mode (default: False)
        stealth_browser (str): 隐身模式浏览器类型（默认 'chrome'）
                              / Stealth mode browser type (default: 'chrome')
            - 可选值：chrome, firefox, safari, edge, chrome_mobile
            - Options: chrome, firefox, safari, edge, chrome_mobile
        delay (tuple, optional): 请求前随机延迟范围（秒），如 (1, 3)
                                / Random delay range before request (seconds), e.g., (1, 3)
        token (str, optional): Workers API 鉴权 token
                               / Workers API authentication token
            - 当 Workers 配置了 TOKEN 环境变量时必填
            - Required when Workers has TOKEN environment variable configured
        **kwargs: 其他参数，与 requests 库完全兼容
                 / Other parameters, fully compatible with requests library
            - data (dict/str): 表单数据 / Form data
            - json (dict): JSON 数据 / JSON data
            - headers (dict): 自定义请求头 / Custom headers
            - cookies (dict): Cookie
            - timeout (int/float): 超时时间（秒），默认 30 / Timeout (seconds), default: 30
    
    Returns:
        CFSpiderResponse: 响应对象 / Response object
    """
    return request("POST", url, cf_proxies=cf_proxies, cf_workers=cf_workers,
                   http2=http2, impersonate=impersonate,
                   map_output=map_output, map_file=map_file,
                   stealth=stealth, stealth_browser=stealth_browser, delay=delay, token=token, **kwargs)


def put(url, cf_proxies=None, cf_workers=True, http2=False, impersonate=None,
        map_output=False, map_file="cfspider_map.html",
        stealth=False, stealth_browser='chrome', delay=None, token=None, **kwargs):
    """
    发送 PUT 请求 / Send PUT request
    
    Args:
        url (str): 目标 URL / Target URL
        cf_proxies (str, optional): 代理地址 / Proxy address
        cf_workers (bool): 是否使用 CFspider Workers API（默认 True）
                          / Whether to use CFspider Workers API (default: True)
        http2 (bool): 是否启用 HTTP/2 协议（默认 False）
                     / Whether to enable HTTP/2 protocol (default: False)
        impersonate (str, optional): TLS 指纹模拟 / TLS fingerprint impersonation
        map_output (bool): 是否生成 IP 地图 HTML 文件（默认 False）
                          / Whether to generate IP map HTML file (default: False)
        map_file (str): 地图输出文件名（默认 "cfspider_map.html"）
                       / Map output filename (default: "cfspider_map.html")
        stealth (bool): 是否启用隐身模式（默认 False）
                       / Whether to enable stealth mode (default: False)
        stealth_browser (str): 隐身模式浏览器类型（默认 'chrome'）
                              / Stealth mode browser type (default: 'chrome')
        delay (tuple, optional): 请求前随机延迟范围（秒），如 (1, 3)
                                / Random delay range before request (seconds), e.g., (1, 3)
        token (str, optional): Workers API 鉴权 token
                               / Workers API authentication token
        **kwargs: 其他参数，与 requests 库完全兼容
                 / Other parameters, fully compatible with requests library
    
    Returns:
        CFSpiderResponse: 响应对象 / Response object
    """
    return request("PUT", url, cf_proxies=cf_proxies, cf_workers=cf_workers,
                   http2=http2, impersonate=impersonate,
                   map_output=map_output, map_file=map_file,
                   stealth=stealth, stealth_browser=stealth_browser, delay=delay, token=token, **kwargs)


def delete(url, cf_proxies=None, cf_workers=True, http2=False, impersonate=None,
           map_output=False, map_file="cfspider_map.html",
           stealth=False, stealth_browser='chrome', delay=None, token=None, **kwargs):
    """
    发送 DELETE 请求 / Send DELETE request
    
    Args:
        url (str): 目标 URL / Target URL
        cf_proxies (str, optional): 代理地址 / Proxy address
        cf_workers (bool): 是否使用 CFspider Workers API（默认 True）
                          / Whether to use CFspider Workers API (default: True)
        http2 (bool): 是否启用 HTTP/2 协议（默认 False）
                     / Whether to enable HTTP/2 protocol (default: False)
        impersonate (str, optional): TLS 指纹模拟 / TLS fingerprint impersonation
        map_output (bool): 是否生成 IP 地图 HTML 文件（默认 False）
                          / Whether to generate IP map HTML file (default: False)
        map_file (str): 地图输出文件名（默认 "cfspider_map.html"）
                       / Map output filename (default: "cfspider_map.html")
        stealth (bool): 是否启用隐身模式（默认 False）
                       / Whether to enable stealth mode (default: False)
        stealth_browser (str): 隐身模式浏览器类型（默认 'chrome'）
                              / Stealth mode browser type (default: 'chrome')
        delay (tuple, optional): 请求前随机延迟范围（秒），如 (1, 3)
                                / Random delay range before request (seconds), e.g., (1, 3)
        token (str, optional): Workers API 鉴权 token
                               / Workers API authentication token
        **kwargs: 其他参数，与 requests 库完全兼容
                 / Other parameters, fully compatible with requests library
    
    Returns:
        CFSpiderResponse: 响应对象 / Response object
    """
    return request("DELETE", url, cf_proxies=cf_proxies, cf_workers=cf_workers,
                   http2=http2, impersonate=impersonate,
                   map_output=map_output, map_file=map_file,
                   stealth=stealth, stealth_browser=stealth_browser, delay=delay, token=token, **kwargs)


def head(url, cf_proxies=None, cf_workers=True, http2=False, impersonate=None,
         map_output=False, map_file="cfspider_map.html",
         stealth=False, stealth_browser='chrome', delay=None, token=None, **kwargs):
    """
    发送 HEAD 请求 / Send HEAD request
    
    Args:
        url (str): 目标 URL / Target URL
        cf_proxies (str, optional): 代理地址 / Proxy address
        cf_workers (bool): 是否使用 CFspider Workers API（默认 True）
                          / Whether to use CFspider Workers API (default: True)
        http2 (bool): 是否启用 HTTP/2 协议（默认 False）
                     / Whether to enable HTTP/2 protocol (default: False)
        impersonate (str, optional): TLS 指纹模拟 / TLS fingerprint impersonation
        map_output (bool): 是否生成 IP 地图 HTML 文件（默认 False）
                          / Whether to generate IP map HTML file (default: False)
        map_file (str): 地图输出文件名（默认 "cfspider_map.html"）
                       / Map output filename (default: "cfspider_map.html")
        stealth (bool): 是否启用隐身模式（默认 False）
                       / Whether to enable stealth mode (default: False)
        stealth_browser (str): 隐身模式浏览器类型（默认 'chrome'）
                              / Stealth mode browser type (default: 'chrome')
        delay (tuple, optional): 请求前随机延迟范围（秒），如 (1, 3)
                                / Random delay range before request (seconds), e.g., (1, 3)
        token (str, optional): Workers API 鉴权 token
                               / Workers API authentication token
        **kwargs: 其他参数，与 requests 库完全兼容
                 / Other parameters, fully compatible with requests library
    
    Returns:
        CFSpiderResponse: 响应对象 / Response object
    """
    return request("HEAD", url, cf_proxies=cf_proxies, cf_workers=cf_workers,
                   http2=http2, impersonate=impersonate,
                   map_output=map_output, map_file=map_file,
                   stealth=stealth, stealth_browser=stealth_browser, delay=delay, token=token, **kwargs)


def options(url, cf_proxies=None, cf_workers=True, http2=False, impersonate=None,
            map_output=False, map_file="cfspider_map.html",
            stealth=False, stealth_browser='chrome', delay=None, token=None, **kwargs):
    """
    发送 OPTIONS 请求 / Send OPTIONS request
    
    Args:
        url (str): 目标 URL / Target URL
        cf_proxies (str, optional): 代理地址 / Proxy address
        cf_workers (bool): 是否使用 CFspider Workers API（默认 True）
                          / Whether to use CFspider Workers API (default: True)
        http2 (bool): 是否启用 HTTP/2 协议（默认 False）
                     / Whether to enable HTTP/2 protocol (default: False)
        impersonate (str, optional): TLS 指纹模拟 / TLS fingerprint impersonation
        map_output (bool): 是否生成 IP 地图 HTML 文件（默认 False）
                          / Whether to generate IP map HTML file (default: False)
        map_file (str): 地图输出文件名（默认 "cfspider_map.html"）
                       / Map output filename (default: "cfspider_map.html")
        stealth (bool): 是否启用隐身模式（默认 False）
                       / Whether to enable stealth mode (default: False)
        stealth_browser (str): 隐身模式浏览器类型（默认 'chrome'）
                              / Stealth mode browser type (default: 'chrome')
        delay (tuple, optional): 请求前随机延迟范围（秒），如 (1, 3)
                                / Random delay range before request (seconds), e.g., (1, 3)
        token (str, optional): Workers API 鉴权 token
                               / Workers API authentication token
        **kwargs: 其他参数，与 requests 库完全兼容
                 / Other parameters, fully compatible with requests library
    
    Returns:
        CFSpiderResponse: 响应对象 / Response object
    """
    return request("OPTIONS", url, cf_proxies=cf_proxies, cf_workers=cf_workers,
                   http2=http2, impersonate=impersonate,
                   map_output=map_output, map_file=map_file,
                   stealth=stealth, stealth_browser=stealth_browser, delay=delay, token=token, **kwargs)


def patch(url, cf_proxies=None, cf_workers=True, http2=False, impersonate=None,
          map_output=False, map_file="cfspider_map.html",
          stealth=False, stealth_browser='chrome', delay=None, token=None, **kwargs):
    """
    发送 PATCH 请求 / Send PATCH request
    
    Args:
        url (str): 目标 URL / Target URL
        cf_proxies (str, optional): 代理地址 / Proxy address
        cf_workers (bool): 是否使用 CFspider Workers API（默认 True）
                          / Whether to use CFspider Workers API (default: True)
        http2 (bool): 是否启用 HTTP/2 协议（默认 False）
                     / Whether to enable HTTP/2 protocol (default: False)
        impersonate (str, optional): TLS 指纹模拟 / TLS fingerprint impersonation
        map_output (bool): 是否生成 IP 地图 HTML 文件（默认 False）
                          / Whether to generate IP map HTML file (default: False)
        map_file (str): 地图输出文件名（默认 "cfspider_map.html"）
                       / Map output filename (default: "cfspider_map.html")
        stealth (bool): 是否启用隐身模式（默认 False）
                       / Whether to enable stealth mode (default: False)
        stealth_browser (str): 隐身模式浏览器类型（默认 'chrome'）
                              / Stealth mode browser type (default: 'chrome')
        delay (tuple, optional): 请求前随机延迟范围（秒），如 (1, 3)
                                / Random delay range before request (seconds), e.g., (1, 3)
        token (str, optional): Workers API 鉴权 token
                               / Workers API authentication token
        **kwargs: 其他参数，与 requests 库完全兼容
                 / Other parameters, fully compatible with requests library
    
    Returns:
        CFSpiderResponse: 响应对象 / Response object
    """
    return request("PATCH", url, cf_proxies=cf_proxies, cf_workers=cf_workers,
                   http2=http2, impersonate=impersonate,
                   map_output=map_output, map_file=map_file,
                   stealth=stealth, stealth_browser=stealth_browser, delay=delay, token=token, **kwargs)


def clear_map_records():
    """清空 IP 地图记录"""
    ip_map.clear_records()


def get_map_collector():
    """获取 IP 地图收集器"""
    return ip_map.get_collector()
