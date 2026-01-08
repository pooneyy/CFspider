"""
CFspider Session 模块

提供会话管理功能，在多个请求之间保持代理配置、请求头和 Cookie。
"""

from .api import request


class Session:
    """
    CFspider 会话类 / CFspider Session class
    
    在多个请求之间保持相同的代理配置、请求头和 Cookie。
    Maintains the same proxy configuration, headers, and cookies across multiple requests.
    适合需要登录状态或连续请求的场景。
    Suitable for scenarios requiring login state or consecutive requests.
    
    Attributes:
        cf_proxies (str): Workers 代理地址 / Workers proxy address
        headers (dict): 会话级别的默认请求头 / Session-level default headers
        cookies (dict): 会话级别的 Cookie / Session-level cookies
        token (str, optional): Workers API 鉴权 token / Workers API authentication token
    
    Example:
        >>> import cfspider
        >>> 
        >>> # 创建会话 / Create session
        >>> with cfspider.Session(cf_proxies="https://your-workers.dev", token="your-token") as session:
        ...     # 设置会话级别的请求头 / Set session-level headers
        ...     session.headers['Authorization'] = 'Bearer token'
        ...     
        ...     # 所有请求都会使用相同的代理和请求头
        ...     # All requests use the same proxy and headers
        ...     response1 = session.get("https://api.example.com/user")
        ...     response2 = session.post("https://api.example.com/data", json={"key": "value"})
        ...     
        ...     # Cookie 会自动保持 / Cookies are automatically maintained
        ...     print(session.cookies)
    
    Note:
        如果需要隐身模式的会话一致性（自动 Referer、随机延迟等），
        If you need stealth mode session consistency (auto Referer, random delay, etc.),
        请使用 cfspider.StealthSession。
        please use cfspider.StealthSession.
    """
    
    def __init__(self, cf_proxies=None, token=None):
        """
        初始化会话 / Initialize session
        
        Args:
            cf_proxies (str): Workers 代理地址（必填）
                            / Workers proxy address (required)
                例如："https://your-workers.dev"
                e.g., "https://your-workers.dev"
            token (str, optional): Workers API 鉴权 token
                                  / Workers API authentication token
                当 Workers 端配置了 TOKEN 环境变量时，必须提供有效的 token
                Required when Workers has TOKEN environment variable configured
        
        Raises:
            ValueError: 当 cf_proxies 为空时
                       / When cf_proxies is empty
        
        Example:
            >>> session = cfspider.Session(cf_proxies="https://your-workers.dev", token="your-token")
        """
        if not cf_proxies:
            raise ValueError(
                "cf_proxies 是必填参数。\n"
                "请提供 CFspider Workers 地址，例如：\n"
                "  session = cfspider.Session(cf_proxies='https://your-workers.dev')\n\n"
                "如果不需要代理，可以直接使用 cfspider.get() 等函数。\n"
                "如果需要隐身模式会话，请使用 cfspider.StealthSession。"
            )
        self.cf_proxies = cf_proxies.rstrip("/")
        self.token = token
        self.headers = {}
        self.cookies = {}
    
    def request(self, method, url, **kwargs):
        """
        发送 HTTP 请求 / Send HTTP request
        
        Args:
            method (str): HTTP 方法（GET, POST, PUT, DELETE 等）
                         / HTTP method (GET, POST, PUT, DELETE, etc.)
            url (str): 目标 URL / Target URL
            **kwargs: 其他参数，与 cfspider.request() 相同
                     / Other parameters, same as cfspider.request()
                - headers (dict): 自定义请求头 / Custom headers
                - cookies (dict): Cookie
                - data (dict/str): 表单数据 / Form data
                - json (dict): JSON 数据 / JSON data
                - timeout (int/float): 超时时间（秒） / Timeout (seconds)
                - 其他参数与 requests 库兼容
                - Other parameters compatible with requests library
        
        Returns:
            CFSpiderResponse: 响应对象 / Response object
        
        Note:
            会话级别的 headers 和 cookies 会自动添加到请求中，
            Session-level headers and cookies are automatically added to requests,
            但请求级别的参数优先级更高。
            but request-level parameters have higher priority.
        """
        headers = self.headers.copy()
        headers.update(kwargs.pop("headers", {}))
        
        cookies = self.cookies.copy()
        cookies.update(kwargs.pop("cookies", {}))
        
        return request(
            method,
            url,
            cf_proxies=self.cf_proxies,
            token=self.token,
            headers=headers,
            cookies=cookies,
            **kwargs
        )
    
    def get(self, url, **kwargs):
        """
        发送 GET 请求 / Send GET request
        
        Args:
            url (str): 目标 URL / Target URL
            **kwargs: 其他参数，与 cfspider.get() 相同
                     / Other parameters, same as cfspider.get()
        
        Returns:
            CFSpiderResponse: 响应对象 / Response object
        """
        return self.request("GET", url, **kwargs)
    
    def post(self, url, **kwargs):
        """
        发送 POST 请求 / Send POST request
        
        Args:
            url (str): 目标 URL / Target URL
            **kwargs: 其他参数，与 cfspider.post() 相同
                     / Other parameters, same as cfspider.post()
        
        Returns:
            CFSpiderResponse: 响应对象 / Response object
        """
        return self.request("POST", url, **kwargs)
    
    def put(self, url, **kwargs):
        """
        发送 PUT 请求 / Send PUT request
        
        Args:
            url (str): 目标 URL / Target URL
            **kwargs: 其他参数，与 cfspider.put() 相同
                     / Other parameters, same as cfspider.put()
        
        Returns:
            CFSpiderResponse: 响应对象 / Response object
        """
        return self.request("PUT", url, **kwargs)
    
    def delete(self, url, **kwargs):
        """
        发送 DELETE 请求 / Send DELETE request
        
        Args:
            url (str): 目标 URL / Target URL
            **kwargs: 其他参数，与 cfspider.delete() 相同
                     / Other parameters, same as cfspider.delete()
        
        Returns:
            CFSpiderResponse: 响应对象 / Response object
        """
        return self.request("DELETE", url, **kwargs)
    
    def head(self, url, **kwargs):
        """
        发送 HEAD 请求 / Send HEAD request
        
        Args:
            url (str): 目标 URL / Target URL
            **kwargs: 其他参数，与 cfspider.head() 相同
                     / Other parameters, same as cfspider.head()
        
        Returns:
            CFSpiderResponse: 响应对象 / Response object
        """
        return self.request("HEAD", url, **kwargs)
    
    def options(self, url, **kwargs):
        """
        发送 OPTIONS 请求 / Send OPTIONS request
        
        Args:
            url (str): 目标 URL / Target URL
            **kwargs: 其他参数，与 cfspider.options() 相同
                     / Other parameters, same as cfspider.options()
        
        Returns:
            CFSpiderResponse: 响应对象 / Response object
        """
        return self.request("OPTIONS", url, **kwargs)
    
    def patch(self, url, **kwargs):
        """
        发送 PATCH 请求 / Send PATCH request
        
        Args:
            url (str): 目标 URL / Target URL
            **kwargs: 其他参数，与 cfspider.patch() 相同
                     / Other parameters, same as cfspider.patch()
        
        Returns:
            CFSpiderResponse: 响应对象 / Response object
        """
        return self.request("PATCH", url, **kwargs)
    
    def close(self):
        """
        关闭会话
        
        当前实现中，每个请求都是独立的，无需特殊清理。
        保留此方法是为了与 requests.Session 保持接口兼容。
        """
        pass
    
    def __enter__(self):
        """支持上下文管理器（with 语句）"""
        return self
    
    def __exit__(self, *args):
        """退出上下文时关闭会话"""
        self.close()

