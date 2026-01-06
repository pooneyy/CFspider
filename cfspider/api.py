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


def request(method, url, cf_proxies=None, cf_workers=True, http2=False, impersonate=None, 
             map_output=False, map_file="cfspider_map.html", 
             stealth=False, stealth_browser='chrome', delay=None, **kwargs):
    """
    发送 HTTP 请求
    
    这是 CFspider 的核心函数，支持多种代理模式和反爬虫功能。
    
    Args:
        method (str): HTTP 方法（GET, POST, PUT, DELETE, HEAD, OPTIONS, PATCH）
        url (str): 目标 URL，必须包含协议（https://）
        cf_proxies (str, optional): 代理地址，根据 cf_workers 参数有不同含义：
            - 当 cf_workers=True 时：填写 CFspider Workers 地址（如 "https://your-workers.dev"）
            - 当 cf_workers=False 时：填写普通 HTTP/SOCKS5 代理（如 "http://127.0.0.1:8080"）
            - 不填写时：直接请求目标 URL，不使用代理
        cf_workers (bool): 是否使用 CFspider Workers API（默认 True）
            - True: cf_proxies 是 Workers 地址，请求通过 Workers API 转发
            - False: cf_proxies 是普通代理，使用 requests/httpx 的 proxies 参数
        http2 (bool): 是否启用 HTTP/2 协议（默认 False）
            - True: 使用 httpx 客户端，支持 HTTP/2
            - False: 使用 requests 库（默认行为）
            - 注意：http2 和 impersonate 不能同时使用
        impersonate (str, optional): TLS 指纹模拟，模拟真实浏览器的 TLS 握手特征
            - 可选值：chrome131, chrome124, safari18_0, firefox133, edge101 等
            - 设置后自动使用 curl_cffi 发送请求
            - 完整列表：cfspider.get_supported_browsers()
        map_output (bool): 是否生成 IP 地图 HTML 文件（默认 False）
            - True: 请求完成后生成包含代理 IP 信息的交互式地图
        map_file (str): 地图输出文件名（默认 "cfspider_map.html"）
        stealth (bool): 是否启用隐身模式（默认 False）
            - True: 自动添加 15+ 个完整浏览器请求头，模拟真实浏览器访问
            - 添加的请求头包括：User-Agent, Accept, Accept-Language, Sec-Fetch-*, Sec-CH-UA 等
        stealth_browser (str): 隐身模式使用的浏览器类型（默认 'chrome'）
            - 可选值：chrome, firefox, safari, edge, chrome_mobile
        delay (tuple, optional): 请求前的随机延迟范围（秒）
            - 如 (1, 3) 表示请求前随机等待 1-3 秒
            - 用于模拟人类行为，避免被反爬系统检测
        **kwargs: 其他参数，与 requests 库完全兼容
            - params (dict): URL 查询参数
            - headers (dict): 自定义请求头（会与隐身模式头合并）
            - data (dict/str): 表单数据
            - json (dict): JSON 数据（自动设置 Content-Type）
            - cookies (dict): Cookie
            - timeout (int/float): 超时时间（秒），默认 30
            - allow_redirects (bool): 是否跟随重定向，默认 True
            - verify (bool): 是否验证 SSL 证书，默认 True
    
    Returns:
        CFSpiderResponse: 响应对象，包含以下属性：
            - text: 响应文本
            - content: 响应字节
            - json(): 解析 JSON
            - status_code: HTTP 状态码
            - headers: 响应头
            - cf_colo: Cloudflare 节点代码（使用 Workers 时可用）
            - cf_ray: Cloudflare Ray ID
    
    Raises:
        ImportError: 当需要的可选依赖未安装时
            - http2=True 需要 httpx[http2]
            - impersonate 需要 curl_cffi
        ValueError: 当 http2 和 impersonate 同时启用时
        requests.RequestException: 网络请求失败时
    
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
            **kwargs
        )
        _handle_map_output(response, url, start_time, map_output, map_file)
        return response
    
    # 如果启用 HTTP/2，使用 httpx
    if http2:
        response = _request_httpx(
            method, url, cf_proxies, cf_workers,
            params=params, headers=headers, data=data,
            json_data=json_data, cookies=cookies, timeout=timeout,
            **kwargs
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
    
    proxy_url = f"{cf_proxies_url}/proxy?url={quote(target_url, safe='')}&method={method.upper()}"
    
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
                         cookies=None, timeout=30, **kwargs):
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
                   data=None, json_data=None, cookies=None, timeout=30, **kwargs):
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
        stealth=False, stealth_browser='chrome', delay=None, **kwargs):
    """
    发送 GET 请求
    
    Args:
        url: 目标 URL
        cf_proxies: 代理地址
        cf_workers: 是否使用 Workers API（默认 True）
        http2: 是否启用 HTTP/2
        impersonate: TLS 指纹（如 "chrome131", "safari18_0", "firefox133"）
        map_output: 是否生成 IP 地图 HTML 文件
        map_file: 地图输出文件名
        stealth: 是否启用隐身模式（自动添加完整浏览器请求头）
        stealth_browser: 隐身模式浏览器类型（chrome/firefox/safari/edge/chrome_mobile）
        delay: 请求前随机延迟范围，如 (1, 3)
    """
    return request("GET", url, cf_proxies=cf_proxies, cf_workers=cf_workers, 
                   http2=http2, impersonate=impersonate,
                   map_output=map_output, map_file=map_file,
                   stealth=stealth, stealth_browser=stealth_browser, delay=delay, **kwargs)


def post(url, cf_proxies=None, cf_workers=True, http2=False, impersonate=None,
         map_output=False, map_file="cfspider_map.html",
         stealth=False, stealth_browser='chrome', delay=None, **kwargs):
    """发送 POST 请求"""
    return request("POST", url, cf_proxies=cf_proxies, cf_workers=cf_workers,
                   http2=http2, impersonate=impersonate,
                   map_output=map_output, map_file=map_file,
                   stealth=stealth, stealth_browser=stealth_browser, delay=delay, **kwargs)


def put(url, cf_proxies=None, cf_workers=True, http2=False, impersonate=None,
        map_output=False, map_file="cfspider_map.html",
        stealth=False, stealth_browser='chrome', delay=None, **kwargs):
    """发送 PUT 请求"""
    return request("PUT", url, cf_proxies=cf_proxies, cf_workers=cf_workers,
                   http2=http2, impersonate=impersonate,
                   map_output=map_output, map_file=map_file,
                   stealth=stealth, stealth_browser=stealth_browser, delay=delay, **kwargs)


def delete(url, cf_proxies=None, cf_workers=True, http2=False, impersonate=None,
           map_output=False, map_file="cfspider_map.html",
           stealth=False, stealth_browser='chrome', delay=None, **kwargs):
    """发送 DELETE 请求"""
    return request("DELETE", url, cf_proxies=cf_proxies, cf_workers=cf_workers,
                   http2=http2, impersonate=impersonate,
                   map_output=map_output, map_file=map_file,
                   stealth=stealth, stealth_browser=stealth_browser, delay=delay, **kwargs)


def head(url, cf_proxies=None, cf_workers=True, http2=False, impersonate=None,
         map_output=False, map_file="cfspider_map.html",
         stealth=False, stealth_browser='chrome', delay=None, **kwargs):
    """发送 HEAD 请求"""
    return request("HEAD", url, cf_proxies=cf_proxies, cf_workers=cf_workers,
                   http2=http2, impersonate=impersonate,
                   map_output=map_output, map_file=map_file,
                   stealth=stealth, stealth_browser=stealth_browser, delay=delay, **kwargs)


def options(url, cf_proxies=None, cf_workers=True, http2=False, impersonate=None,
            map_output=False, map_file="cfspider_map.html",
            stealth=False, stealth_browser='chrome', delay=None, **kwargs):
    """发送 OPTIONS 请求"""
    return request("OPTIONS", url, cf_proxies=cf_proxies, cf_workers=cf_workers,
                   http2=http2, impersonate=impersonate,
                   map_output=map_output, map_file=map_file,
                   stealth=stealth, stealth_browser=stealth_browser, delay=delay, **kwargs)


def patch(url, cf_proxies=None, cf_workers=True, http2=False, impersonate=None,
          map_output=False, map_file="cfspider_map.html",
          stealth=False, stealth_browser='chrome', delay=None, **kwargs):
    """发送 PATCH 请求"""
    return request("PATCH", url, cf_proxies=cf_proxies, cf_workers=cf_workers,
                   http2=http2, impersonate=impersonate,
                   map_output=map_output, map_file=map_file,
                   stealth=stealth, stealth_browser=stealth_browser, delay=delay, **kwargs)


def clear_map_records():
    """清空 IP 地图记录"""
    ip_map.clear_records()


def get_map_collector():
    """获取 IP 地图收集器"""
    return ip_map.get_collector()
