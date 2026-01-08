"""
CFspider 批量请求模块

提供批量请求、并发控制、进度显示和结果聚合功能。

Example:
    >>> import cfspider
    >>> 
    >>> # 基础批量请求
    >>> results = cfspider.batch(["url1", "url2", "url3"])
    >>> 
    >>> # 带数据提取的批量请求
    >>> results = cfspider.batch(
    ...     ["url1", "url2"],
    ...     pick={"title": "h1", "price": ".price"},
    ...     concurrency=5
    ... )
    >>> results.save("output.csv")
"""

import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, List, Dict, Optional, Callable, Union
from dataclasses import dataclass, field

# 延迟导入 tqdm
_tqdm = None


def _get_tqdm():
    """延迟加载 tqdm"""
    global _tqdm
    if _tqdm is None:
        try:
            from tqdm import tqdm
            _tqdm = tqdm
        except ImportError:
            # 如果没有 tqdm，使用简单的进度显示
            _tqdm = None
    return _tqdm


@dataclass
class BatchItem:
    """
    批量请求的单个结果项
    
    Attributes:
        url: 请求的 URL
        data: 提取的数据（如果使用了 pick）
        response: 原始响应对象
        error: 错误信息（如果请求失败）
        duration: 请求耗时（秒）
    """
    url: str
    data: Optional[Dict[str, Any]] = None
    response: Any = None
    error: Optional[str] = None
    duration: float = 0.0
    
    @property
    def success(self) -> bool:
        """请求是否成功"""
        return self.error is None
    
    def __repr__(self):
        if self.success:
            return f"BatchItem(url={self.url!r}, data={self.data})"
        else:
            return f"BatchItem(url={self.url!r}, error={self.error!r})"


class BatchResult:
    """
    批量请求结果集合
    
    支持迭代、过滤和导出功能。
    
    Example:
        >>> results = cfspider.batch(urls, pick={...})
        >>> 
        >>> # 迭代结果
        >>> for item in results:
        ...     print(item.url, item.data)
        >>> 
        >>> # 获取成功/失败的结果
        >>> print(len(results.successful))
        >>> print(len(results.failed))
        >>> 
        >>> # 保存结果
        >>> results.save("output.csv")
    """
    
    def __init__(self, items: List[BatchItem] = None):
        self._items: List[BatchItem] = items or []
    
    def append(self, item: BatchItem):
        """添加结果项"""
        self._items.append(item)
    
    def __iter__(self):
        return iter(self._items)
    
    def __len__(self):
        return len(self._items)
    
    def __getitem__(self, index):
        return self._items[index]
    
    @property
    def successful(self) -> List[BatchItem]:
        """获取成功的结果"""
        return [item for item in self._items if item.success]
    
    @property
    def failed(self) -> List[BatchItem]:
        """获取失败的结果"""
        return [item for item in self._items if not item.success]
    
    @property
    def success_rate(self) -> float:
        """成功率"""
        if not self._items:
            return 0.0
        return len(self.successful) / len(self._items)
    
    def to_list(self) -> List[Dict[str, Any]]:
        """转换为字典列表"""
        results = []
        for item in self._items:
            row = {"url": item.url}
            if item.data:
                row.update(item.data)
            if item.error:
                row["_error"] = item.error
            row["_duration"] = item.duration
            results.append(row)
        return results
    
    def to_dataframe(self):
        """转换为 pandas DataFrame"""
        try:
            import pandas as pd
            return pd.DataFrame(self.to_list())
        except ImportError:
            raise ImportError(
                "pandas is required for to_dataframe(). "
                "Install it with: pip install pandas"
            )
    
    def save(self, filepath: str, **kwargs) -> str:
        """
        保存结果到文件
        
        Args:
            filepath: 输出文件路径（根据扩展名自动选择格式）
            **kwargs: 传递给导出函数的参数
            
        Returns:
            输出文件的绝对路径
        """
        from .export import export
        return export(self.to_list(), filepath, **kwargs)
    
    def filter(self, predicate: Callable[[BatchItem], bool]) -> 'BatchResult':
        """
        过滤结果
        
        Args:
            predicate: 过滤函数
            
        Returns:
            过滤后的 BatchResult
        """
        return BatchResult([item for item in self._items if predicate(item)])
    
    def summary(self) -> Dict[str, Any]:
        """获取结果摘要"""
        total_duration = sum(item.duration for item in self._items)
        return {
            "total": len(self._items),
            "successful": len(self.successful),
            "failed": len(self.failed),
            "success_rate": f"{self.success_rate:.1%}",
            "total_duration": f"{total_duration:.2f}s",
            "avg_duration": f"{total_duration / len(self._items):.2f}s" if self._items else "0s",
        }
    
    def __repr__(self):
        return f"BatchResult({len(self.successful)} successful, {len(self.failed)} failed)"


def batch(
    urls: Union[List[str], str],
    pick: Dict[str, Any] = None,
    concurrency: int = 5,
    delay: float = 0.0,
    retry: int = 0,
    timeout: float = 30.0,
    cf_proxies: str = None,
    token: str = None,
    impersonate: str = None,
    stealth: bool = False,
    stealth_browser: str = None,
    headers: Dict[str, str] = None,
    on_success: Callable = None,
    on_error: Callable = None,
    progress: bool = True,
    **kwargs
) -> BatchResult:
    """
    批量请求多个 URL
    
    Args:
        urls: URL 列表或文件路径
        pick: 数据提取规则（字典），如 {"title": "h1", "price": ".price"}
        concurrency: 并发数
        delay: 请求间隔（秒）
        retry: 失败重试次数
        timeout: 超时时间（秒）
        cf_proxies: Cloudflare Workers 代理地址
        token: 鉴权 token
        impersonate: TLS 指纹模拟
        stealth: 是否启用隐身模式
        stealth_browser: 隐身模式的浏览器类型
        headers: 自定义请求头
        on_success: 成功回调函数 (url, response, data) -> None
        on_error: 错误回调函数 (url, error) -> None
        progress: 是否显示进度条
        **kwargs: 传递给 cfspider.get 的其他参数
        
    Returns:
        BatchResult 对象
        
    Example:
        >>> results = cfspider.batch(
        ...     ["https://example.com", "https://example.org"],
        ...     pick={"title": "h1"},
        ...     concurrency=10,
        ...     progress=True
        ... )
        >>> results.save("output.csv")
    """
    from . import api
    
    # 如果是文件路径，读取 URL 列表
    if isinstance(urls, str):
        with open(urls, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    
    result = BatchResult()
    lock = threading.Lock()
    last_request_time = [0.0]  # 用列表以便在闭包中修改
    
    def process_url(url: str) -> BatchItem:
        """处理单个 URL"""
        # 应用请求延迟
        if delay > 0:
            with lock:
                elapsed = time.time() - last_request_time[0]
                if elapsed < delay:
                    time.sleep(delay - elapsed)
                last_request_time[0] = time.time()
        
        start_time = time.time()
        item = BatchItem(url=url)
        
        for attempt in range(retry + 1):
            try:
                response = api.get(
                    url,
                    cf_proxies=cf_proxies,
                    token=token,
                    impersonate=impersonate,
                    stealth=stealth,
                    stealth_browser=stealth_browser,
                    headers=headers,
                    timeout=timeout,
                    **kwargs
                )
                
                item.response = response
                item.duration = time.time() - start_time
                
                # 数据提取
                if pick:
                    item.data = response.pick(**pick)
                
                # 成功回调
                if on_success:
                    on_success(url, response, item.data)
                
                return item
                
            except Exception as e:
                if attempt < retry:
                    time.sleep(1)  # 重试前等待
                    continue
                
                item.error = str(e)
                item.duration = time.time() - start_time
                
                # 错误回调
                if on_error:
                    on_error(url, e)
                
                return item
        
        return item
    
    # 使用线程池并发请求
    tqdm = _get_tqdm()
    
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = {executor.submit(process_url, url): url for url in urls}
        
        if progress and tqdm:
            # 使用 tqdm 显示进度
            iterator = tqdm(as_completed(futures), total=len(urls), desc="Fetching")
        else:
            iterator = as_completed(futures)
        
        for future in iterator:
            try:
                item = future.result()
                result.append(item)
            except Exception as e:
                url = futures[future]
                result.append(BatchItem(url=url, error=str(e)))
    
    return result


async def abatch(
    urls: Union[List[str], str],
    pick: Dict[str, Any] = None,
    concurrency: int = 10,
    delay: float = 0.0,
    retry: int = 0,
    timeout: float = 30.0,
    cf_proxies: str = None,
    token: str = None,
    impersonate: str = None,
    stealth: bool = False,
    stealth_browser: str = None,
    headers: Dict[str, str] = None,
    on_success: Callable = None,
    on_error: Callable = None,
    progress: bool = True,
    **kwargs
) -> BatchResult:
    """
    异步批量请求多个 URL
    
    参数与 batch() 相同，但使用异步方式执行。
    
    Example:
        >>> results = await cfspider.abatch(
        ...     ["https://example.com", "https://example.org"],
        ...     pick={"title": "h1"},
        ...     concurrency=20
        ... )
    """
    import asyncio
    from . import async_api
    
    # 如果是文件路径，读取 URL 列表
    if isinstance(urls, str):
        with open(urls, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    
    result = BatchResult()
    semaphore = asyncio.Semaphore(concurrency)
    last_request_time = [0.0]
    
    async def process_url(url: str) -> BatchItem:
        """处理单个 URL"""
        async with semaphore:
            # 应用请求延迟
            if delay > 0:
                elapsed = time.time() - last_request_time[0]
                if elapsed < delay:
                    await asyncio.sleep(delay - elapsed)
                last_request_time[0] = time.time()
            
            start_time = time.time()
            item = BatchItem(url=url)
            
            for attempt in range(retry + 1):
                try:
                    response = await async_api.aget(
                        url,
                        cf_proxies=cf_proxies,
                        token=token,
                        impersonate=impersonate,
                        stealth=stealth,
                        stealth_browser=stealth_browser,
                        headers=headers,
                        timeout=timeout,
                        **kwargs
                    )
                    
                    item.response = response
                    item.duration = time.time() - start_time
                    
                    # 数据提取
                    if pick:
                        item.data = response.pick(**pick)
                    
                    # 成功回调
                    if on_success:
                        on_success(url, response, item.data)
                    
                    return item
                    
                except Exception as e:
                    if attempt < retry:
                        await asyncio.sleep(1)
                        continue
                    
                    item.error = str(e)
                    item.duration = time.time() - start_time
                    
                    # 错误回调
                    if on_error:
                        on_error(url, e)
                    
                    return item
            
            return item
    
    # 并发执行所有请求
    tqdm = _get_tqdm()
    tasks = [process_url(url) for url in urls]
    
    if progress and tqdm:
        # 使用 tqdm 显示进度
        for coro in tqdm(asyncio.as_completed(tasks), total=len(urls), desc="Fetching"):
            item = await coro
            result.append(item)
    else:
        items = await asyncio.gather(*tasks, return_exceptions=True)
        for item in items:
            if isinstance(item, Exception):
                result.append(BatchItem(url="", error=str(item)))
            else:
                result.append(item)
    
    return result

