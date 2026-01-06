"""
CFspider TLS 指纹模拟模块

基于 curl_cffi 实现，可模拟各种浏览器的 TLS 指纹，绕过反爬检测。
"""
from urllib.parse import urlencode, quote
from typing import Optional, Dict, Any, List

# 延迟导入 curl_cffi
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


# 支持的浏览器指纹列表
SUPPORTED_BROWSERS = [
    # Chrome
    "chrome99", "chrome100", "chrome101", "chrome104", "chrome107",
    "chrome110", "chrome116", "chrome119", "chrome120", "chrome123",
    "chrome124", "chrome131",
    # Chrome Android
    "chrome99_android", "chrome131_android",
    # Edge
    "edge99", "edge101",
    # Safari
    "safari15_3", "safari15_5", "safari17_0", "safari17_2_ios",
    "safari18_0", "safari18_0_ios",
    # Firefox
    "firefox102", "firefox109", "firefox133"
]


class ImpersonateResponse:
    """TLS 指纹模拟响应对象"""
    
    def __init__(self, response, cf_colo: Optional[str] = None, cf_ray: Optional[str] = None):
        self._response = response
        self.cf_colo = cf_colo
        self.cf_ray = cf_ray
    
    @property
    def text(self) -> str:
        return self._response.text
    
    @property
    def content(self) -> bytes:
        return self._response.content
    
    @property
    def status_code(self) -> int:
        return self._response.status_code
    
    @property
    def headers(self) -> Dict:
        return dict(self._response.headers)
    
    @property
    def cookies(self) -> Dict:
        return dict(self._response.cookies)
    
    @property
    def url(self) -> str:
        return str(self._response.url)
    
    def json(self, **kwargs) -> Any:
        return self._response.json(**kwargs)
    
    def raise_for_status(self) -> None:
        self._response.raise_for_status()


def impersonate_request(
    method: str,
    url: str,
    impersonate: str = "chrome131",
    cf_proxies: Optional[str] = None,
    cf_workers: bool = True,
    **kwargs
) -> ImpersonateResponse:
    """
    使用 TLS 指纹模拟发送请求
    
    Args:
        method: HTTP 方法
        url: 目标 URL
        impersonate: 浏览器指纹（如 chrome131, safari18_0, firefox133）
        cf_proxies: 代理地址（选填）
        cf_workers: 是否使用 CFspider Workers API（默认 True）
        **kwargs: 其他参数
    
    Returns:
        ImpersonateResponse: 响应对象
    
    Example:
        >>> response = cfspider.impersonate_get("https://example.com", impersonate="chrome131")
        >>> print(response.text)
    """
    curl_requests = _get_curl_cffi()
    
    params = kwargs.pop("params", None)
    headers = kwargs.pop("headers", {})
    data = kwargs.pop("data", None)
    json_data = kwargs.pop("json", None)
    cookies = kwargs.pop("cookies", None)
    timeout = kwargs.pop("timeout", 30)
    
    # 验证浏览器指纹
    if impersonate not in SUPPORTED_BROWSERS:
        raise ValueError(
            f"Unsupported browser: {impersonate}. "
            f"Supported browsers: {', '.join(SUPPORTED_BROWSERS[:10])}..."
        )
    
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
        return ImpersonateResponse(response)
    
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
        return ImpersonateResponse(response)
    
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
    
    return ImpersonateResponse(response, cf_colo=cf_colo, cf_ray=cf_ray)


# 便捷方法
def impersonate_get(url: str, impersonate: str = "chrome131", **kwargs) -> ImpersonateResponse:
    """使用 TLS 指纹模拟发送 GET 请求"""
    return impersonate_request("GET", url, impersonate=impersonate, **kwargs)


def impersonate_post(url: str, impersonate: str = "chrome131", **kwargs) -> ImpersonateResponse:
    """使用 TLS 指纹模拟发送 POST 请求"""
    return impersonate_request("POST", url, impersonate=impersonate, **kwargs)


def impersonate_put(url: str, impersonate: str = "chrome131", **kwargs) -> ImpersonateResponse:
    """使用 TLS 指纹模拟发送 PUT 请求"""
    return impersonate_request("PUT", url, impersonate=impersonate, **kwargs)


def impersonate_delete(url: str, impersonate: str = "chrome131", **kwargs) -> ImpersonateResponse:
    """使用 TLS 指纹模拟发送 DELETE 请求"""
    return impersonate_request("DELETE", url, impersonate=impersonate, **kwargs)


def impersonate_head(url: str, impersonate: str = "chrome131", **kwargs) -> ImpersonateResponse:
    """使用 TLS 指纹模拟发送 HEAD 请求"""
    return impersonate_request("HEAD", url, impersonate=impersonate, **kwargs)


def impersonate_options(url: str, impersonate: str = "chrome131", **kwargs) -> ImpersonateResponse:
    """使用 TLS 指纹模拟发送 OPTIONS 请求"""
    return impersonate_request("OPTIONS", url, impersonate=impersonate, **kwargs)


def impersonate_patch(url: str, impersonate: str = "chrome131", **kwargs) -> ImpersonateResponse:
    """使用 TLS 指纹模拟发送 PATCH 请求"""
    return impersonate_request("PATCH", url, impersonate=impersonate, **kwargs)


class ImpersonateSession:
    """
    TLS 指纹模拟会话类
    
    Example:
        >>> with cfspider.ImpersonateSession(impersonate="chrome131") as session:
        >>>     r1 = session.get("https://example.com")
        >>>     r2 = session.post("https://api.example.com", json={"key": "value"})
    """
    
    def __init__(
        self,
        impersonate: str = "chrome131",
        cf_proxies: Optional[str] = None,
        cf_workers: bool = True,
        timeout: float = 30,
        headers: Optional[Dict[str, str]] = None,
        cookies: Optional[Dict[str, str]] = None,
        **kwargs
    ):
        """
        初始化 TLS 指纹模拟会话
        
        Args:
            impersonate: 浏览器指纹（默认 chrome131）
            cf_proxies: 代理地址（选填）
            cf_workers: 是否使用 CFspider Workers API（默认 True）
            timeout: 默认超时时间（秒）
            headers: 默认请求头
            cookies: 默认 Cookies
        """
        curl_requests = _get_curl_cffi()
        
        if impersonate not in SUPPORTED_BROWSERS:
            raise ValueError(
                f"Unsupported browser: {impersonate}. "
                f"Supported browsers: {', '.join(SUPPORTED_BROWSERS[:10])}..."
            )
        
        self.impersonate = impersonate
        self.cf_proxies = cf_proxies
        self.cf_workers = cf_workers
        self.timeout = timeout
        self.headers = headers or {}
        self.cookies = cookies or {}
        self._session = curl_requests.Session(impersonate=impersonate)
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def close(self):
        """关闭会话"""
        if self._session:
            self._session.close()
    
    def request(self, method: str, url: str, **kwargs) -> ImpersonateResponse:
        """发送请求"""
        merged_headers = {**self.headers, **kwargs.pop("headers", {})}
        merged_cookies = {**self.cookies, **kwargs.pop("cookies", {})}
        timeout = kwargs.pop("timeout", self.timeout)
        
        # 如果没有 cf_proxies 或不使用 Workers API，直接请求
        if not self.cf_proxies or not self.cf_workers:
            proxies = None
            if self.cf_proxies and not self.cf_workers:
                proxy_url = self.cf_proxies
                if not proxy_url.startswith(('http://', 'https://', 'socks5://')):
                    proxy_url = f"http://{proxy_url}"
                proxies = {"http": proxy_url, "https": proxy_url}
            
            response = self._session.request(
                method,
                url,
                headers=merged_headers,
                cookies=merged_cookies,
                timeout=timeout,
                proxies=proxies,
                **kwargs
            )
            return ImpersonateResponse(response)
        
        # 使用 CFspider Workers API 代理
        cf_proxies_url = self.cf_proxies.rstrip("/")
        
        if not cf_proxies_url.startswith(('http://', 'https://')):
            cf_proxies_url = f"https://{cf_proxies_url}"
        
        params = kwargs.pop("params", None)
        target_url = url
        if params:
            target_url = f"{url}?{urlencode(params)}"
        
        proxy_url = f"{cf_proxies_url}/proxy?url={quote(target_url, safe='')}&method={method.upper()}"
        
        request_headers = {}
        for key, value in merged_headers.items():
            request_headers[f"X-CFSpider-Header-{key}"] = value
        
        if merged_cookies:
            cookie_str = "; ".join([f"{k}={v}" for k, v in merged_cookies.items()])
            request_headers["X-CFSpider-Header-Cookie"] = cookie_str
        
        response = self._session.post(
            proxy_url,
            headers=request_headers,
            timeout=timeout,
            **kwargs
        )
        
        cf_colo = response.headers.get("X-CF-Colo")
        cf_ray = response.headers.get("CF-Ray")
        
        return ImpersonateResponse(response, cf_colo=cf_colo, cf_ray=cf_ray)
    
    def get(self, url: str, **kwargs) -> ImpersonateResponse:
        """GET 请求"""
        return self.request("GET", url, **kwargs)
    
    def post(self, url: str, **kwargs) -> ImpersonateResponse:
        """POST 请求"""
        return self.request("POST", url, **kwargs)
    
    def put(self, url: str, **kwargs) -> ImpersonateResponse:
        """PUT 请求"""
        return self.request("PUT", url, **kwargs)
    
    def delete(self, url: str, **kwargs) -> ImpersonateResponse:
        """DELETE 请求"""
        return self.request("DELETE", url, **kwargs)
    
    def head(self, url: str, **kwargs) -> ImpersonateResponse:
        """HEAD 请求"""
        return self.request("HEAD", url, **kwargs)
    
    def options(self, url: str, **kwargs) -> ImpersonateResponse:
        """OPTIONS 请求"""
        return self.request("OPTIONS", url, **kwargs)
    
    def patch(self, url: str, **kwargs) -> ImpersonateResponse:
        """PATCH 请求"""
        return self.request("PATCH", url, **kwargs)


def get_supported_browsers() -> List[str]:
    """获取支持的浏览器指纹列表"""
    return SUPPORTED_BROWSERS.copy()

