"""
CFspider 数据提取模块

提供 CSS 选择器、XPath、JSONPath 数据提取功能。

Example:
    >>> import cfspider
    >>> response = cfspider.get("https://example.com")
    >>> 
    >>> # CSS 选择器
    >>> title = response.find("h1")
    >>> links = response.find_all("a", attr="href")
    >>> 
    >>> # XPath
    >>> items = response.xpath("//div[@class='item']")
    >>> 
    >>> # 批量提取
    >>> data = response.pick(title="h1", links=("a", "href"))
"""

import re
import json
from typing import Any, Optional, Union, List, Dict, Callable

# 延迟导入可选依赖
_bs4 = None
_lxml = None
_jsonpath_ng = None


def _get_bs4():
    """延迟加载 BeautifulSoup"""
    global _bs4
    if _bs4 is None:
        try:
            from bs4 import BeautifulSoup
            _bs4 = BeautifulSoup
        except ImportError:
            raise ImportError(
                "beautifulsoup4 is required for HTML extraction. "
                "Install it with: pip install beautifulsoup4"
            )
    return _bs4


def _get_lxml():
    """延迟加载 lxml"""
    global _lxml
    if _lxml is None:
        try:
            from lxml import etree
            _lxml = etree
        except ImportError:
            raise ImportError(
                "lxml is required for XPath extraction. "
                "Install it with: pip install lxml"
            )
    return _lxml


def _get_jsonpath():
    """延迟加载 jsonpath-ng"""
    global _jsonpath_ng
    if _jsonpath_ng is None:
        try:
            from jsonpath_ng import parse
            _jsonpath_ng = parse
        except ImportError:
            raise ImportError(
                "jsonpath-ng is required for JSONPath extraction. "
                "Install it with: pip install jsonpath-ng"
            )
    return _jsonpath_ng


class Element:
    """
    HTML 元素封装类，支持链式操作
    
    Example:
        >>> element = response.css_one("#product")
        >>> title = element.find("h1")
        >>> price = element.find(".price")
        >>> element.text  # 获取文本
        >>> element.html  # 获取 HTML
        >>> element["href"]  # 获取属性
    """
    
    def __init__(self, element, parser: str = "bs4"):
        """
        初始化元素
        
        Args:
            element: BeautifulSoup Tag 或 lxml Element
            parser: 解析器类型 ("bs4" 或 "lxml")
        """
        self._element = element
        self._parser = parser
    
    @property
    def text(self) -> str:
        """获取元素文本内容"""
        if self._element is None:
            return ""
        if self._parser == "bs4":
            return self._element.get_text(strip=True)
        else:
            return self._element.text_content().strip() if hasattr(self._element, 'text_content') else str(self._element)
    
    @property
    def html(self) -> str:
        """获取元素 HTML 内容"""
        if self._element is None:
            return ""
        if self._parser == "bs4":
            return str(self._element)
        else:
            etree = _get_lxml()
            return etree.tostring(self._element, encoding='unicode')
    
    @property
    def attrs(self) -> Dict[str, str]:
        """获取所有属性"""
        if self._element is None:
            return {}
        if self._parser == "bs4":
            return dict(self._element.attrs) if hasattr(self._element, 'attrs') else {}
        else:
            return dict(self._element.attrib) if hasattr(self._element, 'attrib') else {}
    
    def __getitem__(self, key: str) -> Optional[str]:
        """获取属性值"""
        return self.attrs.get(key)
    
    def get(self, key: str, default: str = None) -> Optional[str]:
        """获取属性值，支持默认值"""
        return self.attrs.get(key, default)
    
    def find(self, selector: str, attr: str = None, strip: bool = True) -> Optional[str]:
        """
        在当前元素内查找第一个匹配的元素
        
        Args:
            selector: CSS 选择器
            attr: 要提取的属性名，None 表示提取文本
            strip: 是否去除空白
            
        Returns:
            匹配元素的文本或属性值
        """
        if self._element is None:
            return None
        
        if self._parser == "bs4":
            found = self._element.select_one(selector)
            if found is None:
                return None
            if attr:
                return found.get(attr)
            text = found.get_text(strip=strip)
            return text
        else:
            # lxml 使用 cssselect
            try:
                from lxml.cssselect import CSSSelector
                sel = CSSSelector(selector)
                results = sel(self._element)
                if not results:
                    return None
                found = results[0]
                if attr:
                    return found.get(attr)
                text = found.text_content()
                return text.strip() if strip and text else text
            except ImportError:
                raise ImportError("cssselect is required for CSS selectors with lxml")
    
    def find_all(self, selector: str, attr: str = None, strip: bool = True) -> List[str]:
        """
        在当前元素内查找所有匹配的元素
        
        Args:
            selector: CSS 选择器
            attr: 要提取的属性名，None 表示提取文本
            strip: 是否去除空白
            
        Returns:
            匹配元素的文本或属性值列表
        """
        if self._element is None:
            return []
        
        results = []
        if self._parser == "bs4":
            elements = self._element.select(selector)
            for el in elements:
                if attr:
                    val = el.get(attr)
                    if val:
                        results.append(val)
                else:
                    text = el.get_text(strip=strip)
                    if text:
                        results.append(text)
        else:
            try:
                from lxml.cssselect import CSSSelector
                sel = CSSSelector(selector)
                elements = sel(self._element)
                for el in elements:
                    if attr:
                        val = el.get(attr)
                        if val:
                            results.append(val)
                    else:
                        text = el.text_content()
                        if text:
                            results.append(text.strip() if strip else text)
            except ImportError:
                raise ImportError("cssselect is required for CSS selectors with lxml")
        
        return results
    
    def css_one(self, selector: str) -> 'Element':
        """返回第一个匹配的 Element 对象，支持链式操作"""
        if self._element is None:
            return Element(None, self._parser)
        
        if self._parser == "bs4":
            found = self._element.select_one(selector)
            return Element(found, self._parser)
        else:
            try:
                from lxml.cssselect import CSSSelector
                sel = CSSSelector(selector)
                results = sel(self._element)
                found = results[0] if results else None
                return Element(found, self._parser)
            except ImportError:
                raise ImportError("cssselect is required for CSS selectors with lxml")
    
    def __bool__(self) -> bool:
        """检查元素是否存在"""
        return self._element is not None
    
    def __str__(self) -> str:
        return self.text
    
    def __repr__(self) -> str:
        if self._element is None:
            return "Element(None)"
        return f"Element({self.html[:50]}...)" if len(self.html) > 50 else f"Element({self.html})"


class ExtractResult(dict):
    """
    提取结果封装，支持直接保存
    
    Example:
        >>> data = response.pick(title="h1", price=".price")
        >>> data.save("output.csv")
        >>> data.save("output.json")
    """
    
    def __init__(self, data: Dict[str, Any], url: str = None):
        super().__init__(data)
        self.url = url
    
    def save(self, filepath: str, **kwargs):
        """
        保存提取结果到文件
        
        Args:
            filepath: 输出文件路径（根据扩展名自动选择格式）
            **kwargs: 传递给导出函数的参数
        """
        from .export import export
        export(dict(self), filepath, **kwargs)
    
    def to_json(self, **kwargs) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(dict(self), ensure_ascii=False, indent=2, **kwargs)


class Extractor:
    """
    数据提取器，支持 CSS 选择器、XPath、JSONPath
    
    Example:
        >>> extractor = Extractor(html_content)
        >>> title = extractor.css("h1")
        >>> links = extractor.css_all("a", attr="href")
    """
    
    def __init__(self, content: Union[str, bytes], content_type: str = "html"):
        """
        初始化提取器
        
        Args:
            content: HTML 或 JSON 内容
            content_type: 内容类型 ("html", "json")
        """
        self.content = content if isinstance(content, str) else content.decode('utf-8', errors='replace')
        self.content_type = content_type
        self._soup = None
        self._lxml_doc = None
        self._json_data = None
    
    def _get_soup(self):
        """获取 BeautifulSoup 对象"""
        if self._soup is None:
            BeautifulSoup = _get_bs4()
            self._soup = BeautifulSoup(self.content, 'html.parser')
        return self._soup
    
    def _get_lxml_doc(self):
        """获取 lxml 文档对象"""
        if self._lxml_doc is None:
            etree = _get_lxml()
            self._lxml_doc = etree.HTML(self.content)
        return self._lxml_doc
    
    def _get_json(self):
        """获取 JSON 数据"""
        if self._json_data is None:
            self._json_data = json.loads(self.content)
        return self._json_data
    
    # ========== 简洁 API ==========
    
    def find(self, selector: str, attr: str = None, strip: bool = True, 
             regex: str = None, parser: Callable = None) -> Optional[str]:
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
        # 自动识别选择器类型
        if selector.startswith('$'):
            result = self.jpath(selector)
        elif selector.startswith('//') or selector.startswith('(//'):
            result = self.xpath(selector)
        else:
            result = self.css(selector, attr=attr, strip=strip)
        
        # 应用正则表达式
        if regex and result:
            match = re.search(regex, str(result))
            result = match.group(0) if match else None
        
        # 应用自定义解析函数
        if parser and result:
            result = parser(result)
        
        return result
    
    def find_all(self, selector: str, attr: str = None, strip: bool = True) -> List[str]:
        """
        查找所有匹配的元素
        
        Args:
            selector: 选择器（CSS/XPath/JSONPath）
            attr: 要提取的属性名
            strip: 是否去除空白
            
        Returns:
            匹配的文本或属性值列表
        """
        if selector.startswith('$'):
            return self.jpath_all(selector)
        elif selector.startswith('//') or selector.startswith('(//'):
            return self.xpath_all(selector)
        else:
            return self.css_all(selector, attr=attr, strip=strip)
    
    # ========== CSS 选择器 ==========
    
    def css(self, selector: str, attr: str = None, html: bool = False, strip: bool = True) -> Optional[str]:
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
        soup = self._get_soup()
        element = soup.select_one(selector)
        
        if element is None:
            return None
        
        if attr:
            return element.get(attr)
        if html:
            return str(element)
        
        text = element.get_text(strip=strip)
        return text
    
    def css_all(self, selector: str, attr: str = None, html: bool = False, strip: bool = True) -> List[str]:
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
        soup = self._get_soup()
        elements = soup.select(selector)
        
        results = []
        for el in elements:
            if attr:
                val = el.get(attr)
                if val:
                    results.append(val)
            elif html:
                results.append(str(el))
            else:
                text = el.get_text(strip=strip)
                if text:
                    results.append(text)
        
        return results
    
    def css_one(self, selector: str) -> Element:
        """
        返回第一个匹配的 Element 对象，支持链式操作
        
        Args:
            selector: CSS 选择器
            
        Returns:
            Element 对象
        """
        soup = self._get_soup()
        element = soup.select_one(selector)
        return Element(element, "bs4")
    
    # ========== XPath ==========
    
    def xpath(self, expression: str) -> Optional[str]:
        """
        使用 XPath 表达式提取第一个匹配
        
        Args:
            expression: XPath 表达式
            
        Returns:
            匹配的文本或属性值
        """
        doc = self._get_lxml_doc()
        results = doc.xpath(expression)
        
        if not results:
            return None
        
        result = results[0]
        if hasattr(result, 'text_content'):
            return result.text_content().strip()
        return str(result).strip() if result else None
    
    def xpath_all(self, expression: str) -> List[str]:
        """
        使用 XPath 表达式提取所有匹配
        
        Args:
            expression: XPath 表达式
            
        Returns:
            匹配的文本或属性值列表
        """
        doc = self._get_lxml_doc()
        results = doc.xpath(expression)
        
        extracted = []
        for result in results:
            if hasattr(result, 'text_content'):
                text = result.text_content().strip()
                if text:
                    extracted.append(text)
            elif result:
                extracted.append(str(result).strip())
        
        return extracted
    
    def xpath_one(self, expression: str) -> Element:
        """
        返回第一个匹配的 Element 对象
        
        Args:
            expression: XPath 表达式
            
        Returns:
            Element 对象
        """
        doc = self._get_lxml_doc()
        results = doc.xpath(expression)
        element = results[0] if results else None
        return Element(element, "lxml")
    
    # ========== JSONPath ==========
    
    def jpath(self, expression: str) -> Any:
        """
        使用 JSONPath 表达式提取第一个匹配
        
        Args:
            expression: JSONPath 表达式（如 $.data.items[0].name）
            
        Returns:
            匹配的值
        """
        parse = _get_jsonpath()
        data = self._get_json()
        
        # 处理简化的点号路径（如 data.items.*.name）
        if not expression.startswith('$'):
            expression = '$.' + expression
        
        jsonpath_expr = parse(expression)
        matches = jsonpath_expr.find(data)
        
        if not matches:
            return None
        
        return matches[0].value
    
    def jpath_all(self, expression: str) -> List[Any]:
        """
        使用 JSONPath 表达式提取所有匹配
        
        Args:
            expression: JSONPath 表达式
            
        Returns:
            匹配的值列表
        """
        parse = _get_jsonpath()
        data = self._get_json()
        
        if not expression.startswith('$'):
            expression = '$.' + expression
        
        jsonpath_expr = parse(expression)
        matches = jsonpath_expr.find(data)
        
        return [match.value for match in matches]
    
    # ========== 批量提取 ==========
    
    def pick(self, **fields) -> ExtractResult:
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
        result = {}
        
        for field_name, selector_spec in fields.items():
            try:
                if isinstance(selector_spec, str):
                    # 简单字符串选择器
                    result[field_name] = self.find(selector_spec)
                
                elif isinstance(selector_spec, tuple):
                    if len(selector_spec) == 2:
                        selector, attr = selector_spec
                        if attr == "text":
                            result[field_name] = self.find(selector)
                        else:
                            result[field_name] = self.find(selector, attr=attr)
                    
                    elif len(selector_spec) == 3:
                        selector, attr, converter = selector_spec
                        if attr == "text":
                            value = self.find(selector)
                        else:
                            value = self.find(selector, attr=attr)
                        
                        if value is not None and converter:
                            try:
                                value = converter(value)
                            except (ValueError, TypeError):
                                pass
                        result[field_name] = value
                    
                    else:
                        result[field_name] = None
                
                else:
                    result[field_name] = None
                    
            except Exception:
                result[field_name] = None
        
        return ExtractResult(result)
    
    def extract(self, rules: Dict[str, str]) -> ExtractResult:
        """
        使用规则字典提取数据（支持前缀指定类型）
        
        Args:
            rules: 字段名到选择器的映射
                选择器可以带前缀指定类型：
                - "css:h1.title" 或直接 "h1.title"
                - "xpath://a/@href"
                - "jsonpath:$.data.name"
                - 添加 "::text" 后缀提取文本
                - 添加 "::html" 后缀提取 HTML
                - 添加 "@attr" 提取属性
                
        Returns:
            ExtractResult 字典
            
        Example:
            >>> result = response.extract({
            ...     "title": "h1.title",
            ...     "links": "xpath://a/@href",
            ...     "api_data": "jsonpath:$.items[*].id"
            ... })
        """
        result = {}
        
        for field_name, selector in rules.items():
            try:
                # 解析选择器
                extract_html = False
                attr = None
                
                # 检查后缀
                if "::text" in selector:
                    selector = selector.replace("::text", "")
                elif "::html" in selector:
                    selector = selector.replace("::html", "")
                    extract_html = True
                
                # 检查属性提取 @attr
                if "@" in selector and not selector.startswith("xpath:"):
                    parts = selector.rsplit("@", 1)
                    selector = parts[0]
                    attr = parts[1]
                
                # 检查前缀
                if selector.startswith("css:"):
                    selector = selector[4:]
                    if extract_html:
                        result[field_name] = self.css(selector, html=True)
                    elif attr:
                        result[field_name] = self.css(selector, attr=attr)
                    else:
                        result[field_name] = self.css(selector)
                
                elif selector.startswith("xpath:"):
                    selector = selector[6:]
                    result[field_name] = self.xpath(selector)
                
                elif selector.startswith("jsonpath:"):
                    selector = selector[9:]
                    result[field_name] = self.jpath(selector)
                
                else:
                    # 默认使用 find（自动识别）
                    result[field_name] = self.find(selector, attr=attr)
                    
            except Exception:
                result[field_name] = None
        
        return ExtractResult(result)


def create_extractor(content: Union[str, bytes], content_type: str = "html") -> Extractor:
    """
    创建数据提取器
    
    Args:
        content: HTML 或 JSON 内容
        content_type: 内容类型
        
    Returns:
        Extractor 实例
    """
    return Extractor(content, content_type)

