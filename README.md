# CFspider

基于 Cloudflare Workers 的代理 IP 池，使用 Cloudflare 全球边缘节点 IP 作为代理出口。

## 特性

- 使用 Cloudflare 全球 300+ 边缘节点 IP
- 与 requests 库语法一致，无学习成本
- 支持 GET、POST、PUT、DELETE 等所有 HTTP 方法
- 支持 Session 会话管理
- 返回 Cloudflare 节点信息（cf_colo、cf_ray）
- **支持浏览器模式**，可渲染 JavaScript 动态页面、截图、自动化操作
- 完全免费，Workers 免费版每日 100,000 请求

## 部署 Workers

1. 登录 [Cloudflare Dashboard](https://dash.cloudflare.com/)
2. 进入 Workers & Pages
3. 点击 Create application → Create Worker
4. 将 `workers.js` 代码粘贴到编辑器中
5. 点击 Deploy

部署完成后，你将获得一个 Workers 地址，如 `https://xxx.username.workers.dev`

如需自定义域名，可在 Worker → Settings → Triggers → Custom Domain 中添加。

## 安装

### 方式一：PyPI 安装（推荐）

```bash
pip install cfspider
```

> **注意**：Python 3.11+ 在 Debian/Ubuntu 上可能提示 `externally-managed-environment` 错误，请使用以下任一方式解决：
> 
> ```bash
> # 方式 A：使用虚拟环境（推荐）
> python3 -m venv venv
> source venv/bin/activate
> pip install cfspider
> 
> # 方式 B：使用 pipx
> pipx install cfspider
> 
> # 方式 C：强制安装（不推荐）
> pip install cfspider --break-system-packages
> ```

### 方式二：国内镜像源安装

如果 PyPI 访问较慢，可使用国内镜像：

```bash
# 清华源
pip install cfspider -i https://pypi.tuna.tsinghua.edu.cn/simple

# 阿里云源
pip install cfspider -i https://mirrors.aliyun.com/pypi/simple

# 中科大源
pip install cfspider -i https://pypi.mirrors.ustc.edu.cn/simple
```

### 方式三：从 GitHub 安装

```bash
pip install git+https://github.com/violettoolssite/CFspider.git
```

### 方式四：手动安装

从官网下载 `cfspider.zip` 后解压：

```bash
# 下载地址：https://spider.violetteam.cloud/cfspider.zip
unzip cfspider.zip
pip install ./cfspider
```

## 快速开始

```python
import cfspider

cf_proxies = "https://your-workers.dev"

response = cfspider.get("https://httpbin.org/ip", cf_proxies=cf_proxies)

print(response.text)
```

## API 参考

### 请求方法

CFspider 支持以下 HTTP 方法，语法与 requests 库一致：

```python
import cfspider

cf_proxies = "https://your-workers.dev"

cfspider.get(url, cf_proxies=cf_proxies)
cfspider.post(url, cf_proxies=cf_proxies, json=data)
cfspider.put(url, cf_proxies=cf_proxies, data=data)
cfspider.delete(url, cf_proxies=cf_proxies)
cfspider.head(url, cf_proxies=cf_proxies)
cfspider.options(url, cf_proxies=cf_proxies)
cfspider.patch(url, cf_proxies=cf_proxies, json=data)
```

### 请求参数

| 参数 | 类型 | 说明 |
|------|------|------|
| url | str | 目标 URL |
| cf_proxies | str | Workers 地址（必填） |
| params | dict | URL 查询参数 |
| data | dict/str | 表单数据 |
| json | dict | JSON 数据 |
| headers | dict | 请求头 |
| cookies | dict | Cookies |
| timeout | int/float | 超时时间（秒） |

### 响应对象

| 属性 | 类型 | 说明 |
|------|------|------|
| text | str | 响应文本 |
| content | bytes | 响应字节 |
| json() | dict | 解析 JSON |
| status_code | int | HTTP 状态码 |
| headers | dict | 响应头 |
| cf_colo | str | Cloudflare 节点代码（如 NRT） |
| cf_ray | str | Cloudflare Ray ID |

## 使用示例

### GET 请求

```python
import cfspider

cf_proxies = "https://your-workers.dev"

response = cfspider.get(
    "https://httpbin.org/get",
    cf_proxies=cf_proxies,
    params={"key": "value"}
)

print(response.status_code)
print(response.json())
```

### POST 请求

```python
import cfspider

cf_proxies = "https://your-workers.dev"

response = cfspider.post(
    "https://httpbin.org/post",
    cf_proxies=cf_proxies,
    json={"name": "cfspider", "version": "1.0"}
)

print(response.json())
```

### 使用 Session

Session 可以复用 Workers 地址，无需每次请求都指定：

```python
import cfspider

cf_proxies = "https://your-workers.dev"

session = cfspider.Session(cf_proxies=cf_proxies)

r1 = session.get("https://httpbin.org/ip")
r2 = session.post("https://httpbin.org/post", json={"test": 1})
r3 = session.get("https://example.com")

print(r1.text)
print(r2.json())

session.close()
```

### 获取 Cloudflare 节点信息

```python
import cfspider

cf_proxies = "https://your-workers.dev"

response = cfspider.get("https://httpbin.org/ip", cf_proxies=cf_proxies)

print(f"出口 IP: {response.json()['origin']}")
print(f"节点代码: {response.cf_colo}")
print(f"Ray ID: {response.cf_ray}")
```

### 自定义请求头

```python
import cfspider

cf_proxies = "https://your-workers.dev"

response = cfspider.get(
    "https://httpbin.org/headers",
    cf_proxies=cf_proxies,
    headers={
        "User-Agent": "MyApp/1.0",
        "Accept-Language": "zh-CN"
    }
)

print(response.json())
```

### 设置超时

```python
import cfspider

cf_proxies = "https://your-workers.dev"

response = cfspider.get(
    "https://httpbin.org/delay/5",
    cf_proxies=cf_proxies,
    timeout=10
)
```

## 错误处理

```python
import cfspider

cf_proxies = "https://your-workers.dev"

try:
    response = cfspider.get("https://httpbin.org/ip", cf_proxies=cf_proxies)
    response.raise_for_status()
    print(response.text)
except cfspider.CFSpiderError as e:
    print(f"请求失败: {e}")
except Exception as e:
    print(f"其他错误: {e}")
```

## 浏览器模式

CFspider 支持浏览器模式，可以渲染 JavaScript 动态页面、截图、生成 PDF、自动化操作等。

### 安装浏览器

首先安装浏览器功能依赖和 Chromium：

```bash
# 安装带浏览器支持的 cfspider
pip install cfspider[browser]

# 安装 Chromium 浏览器
cfspider install
```

或者使用 Python 代码安装：

```python
import cfspider
cfspider.install_browser()
```

### 获取渲染后的 HTML

```python
import cfspider

# 通过 edgetunnel Workers 代理（使用 Cloudflare IP 出口）
browser = cfspider.Browser(
    cf_proxies="v2.kami666.xyz",  # 你的 edgetunnel Workers 地址
    vless_uuid="你的-vless-uuid"   # 你的 VLESS UUID
)

# 获取 JavaScript 渲染后的完整 HTML
html = browser.html("https://example.com")
print(html)

browser.close()

# 也可以直接使用（无代理）
# browser = cfspider.Browser()
```

### 页面截图

```python
import cfspider

browser = cfspider.Browser()

# 截图并保存
browser.screenshot("https://example.com", "screenshot.png")

# 截取整个页面
browser.screenshot("https://example.com", "full.png", full_page=True)

browser.close()
```

### 生成 PDF

```python
import cfspider

browser = cfspider.Browser()

# 生成 PDF（仅无头模式可用）
browser.pdf("https://example.com", "page.pdf")

browser.close()
```

### 自动化操作

```python
import cfspider

browser = cfspider.Browser()

# 打开页面，返回 Playwright Page 对象
page = browser.get("https://example.com")

# 点击元素
page.click("button#submit")

# 填写表单
page.fill("input#username", "myname")
page.fill("input#password", "mypassword")

# 等待元素
page.wait_for_selector(".result")

# 获取文本
text = page.inner_text(".result")
print(text)

browser.close()
```

### 执行 JavaScript

```python
import cfspider

browser = cfspider.Browser()

# 在页面中执行 JavaScript
result = browser.execute_script("https://example.com", "return document.title")
print(result)

browser.close()
```

### 使用 with 语句

```python
import cfspider

with cfspider.Browser() as browser:
    html = browser.html("https://example.com")
    print(html)
# 自动关闭浏览器
```

### 非无头模式

```python
import cfspider

# headless=False 可以看到浏览器窗口
browser = cfspider.Browser(headless=False)

page = browser.get("https://example.com")
# 可以看到浏览器操作

browser.close()
```

## 注意事项

1. Workers 免费版限制：每日 100,000 请求，单次 CPU 时间 10ms
2. 请求体大小限制：免费版 100MB，付费版无限制
3. 超时限制：免费版 30 秒，付费版无限制
4. 不支持 WebSocket、gRPC 等非 HTTP 协议
5. 浏览器模式需要额外安装 `playwright` 和 Chromium

## License

MIT License

## 链接

- GitHub: https://github.com/violettoolssite/CFspider
- PyPI: https://pypi.org/project/cfspider/
- 官网: https://spider.violetteam.cloud
