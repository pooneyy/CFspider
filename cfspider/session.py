"""
CFspider Session 模块

提供会话管理功能，在多个请求之间保持代理配置、请求头和 Cookie。
"""

from .api import request


class Session:
    """
    CFspider 会话类
    
    在多个请求之间保持相同的代理配置、请求头和 Cookie。
    适合需要登录状态或连续请求的场景。
    
    Attributes:
        cf_proxies (str): Workers 代理地址
        headers (dict): 会话级别的默认请求头
        cookies (dict): 会话级别的 Cookie
    
    Example:
        >>> import cfspider
        >>> 
        >>> # 创建会话
        >>> with cfspider.Session(cf_proxies="https://your-workers.dev") as session:
        ...     # 设置会话级别的请求头
        ...     session.headers['Authorization'] = 'Bearer token'
        ...     
        ...     # 所有请求都会使用相同的代理和请求头
        ...     response1 = session.get("https://api.example.com/user")
        ...     response2 = session.post("https://api.example.com/data", json={"key": "value"})
        ...     
        ...     # Cookie 会自动保持
        ...     print(session.cookies)
    
    Note:
        如果需要隐身模式的会话一致性（自动 Referer、随机延迟等），
        请使用 cfspider.StealthSession。
    """
    
    def __init__(self, cf_proxies=None):
        """
        初始化会话
        
        Args:
            cf_proxies (str): Workers 代理地址（必填）
                例如："https://your-workers.dev"
        
        Raises:
            ValueError: 当 cf_proxies 为空时
        
        Example:
            >>> session = cfspider.Session(cf_proxies="https://your-workers.dev")
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
        self.headers = {}
        self.cookies = {}
    
    def request(self, method, url, **kwargs):
        """
        发送 HTTP 请求
        
        Args:
            method (str): HTTP 方法（GET, POST, PUT, DELETE 等）
            url (str): 目标 URL
            **kwargs: 其他参数，与 cfspider.request() 相同
        
        Returns:
            CFSpiderResponse: 响应对象
        
        Note:
            会话级别的 headers 和 cookies 会自动添加到请求中，
            但请求级别的参数优先级更高。
        """
        headers = self.headers.copy()
        headers.update(kwargs.pop("headers", {}))
        
        cookies = self.cookies.copy()
        cookies.update(kwargs.pop("cookies", {}))
        
        return request(
            method,
            url,
            cf_proxies=self.cf_proxies,
            headers=headers,
            cookies=cookies,
            **kwargs
        )
    
    def get(self, url, **kwargs):
        """发送 GET 请求"""
        return self.request("GET", url, **kwargs)
    
    def post(self, url, **kwargs):
        """发送 POST 请求"""
        return self.request("POST", url, **kwargs)
    
    def put(self, url, **kwargs):
        """发送 PUT 请求"""
        return self.request("PUT", url, **kwargs)
    
    def delete(self, url, **kwargs):
        """发送 DELETE 请求"""
        return self.request("DELETE", url, **kwargs)
    
    def head(self, url, **kwargs):
        """发送 HEAD 请求"""
        return self.request("HEAD", url, **kwargs)
    
    def options(self, url, **kwargs):
        """发送 OPTIONS 请求"""
        return self.request("OPTIONS", url, **kwargs)
    
    def patch(self, url, **kwargs):
        """发送 PATCH 请求"""
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

