# CFspider

基于 Cloudflare Workers 的代理 IP 池，使用 Cloudflare 全球边缘节点 IP 作为代理出口。

## 代理方案对比

| 代理方案 | 价格 | IP 质量 | 速度 | 稳定性 | IP 数量 | 反爬能力 |
|---------|------|---------|------|--------|---------|----------|
| **CFspider (Workers)** | **免费** | **企业级** | **极快** | **99.9%** | **300+ 节点** | **强** |
| 直接爬取 CF CDN IP | 免费 | 无法使用 | - | 无法连接 | 理论很多 | 无 |
| 住宅代理 / 家庭代理 | $5-15/GB | 极高 | 中等 | 中等 | 百万+ | 极强 |
| 数据中心代理 | $1-5/月 | 中等 | 快 | 高 | 有限 | 中等 |
| 免费公共代理 | 免费 | 极差 | 慢 | <10% | 数千 | 弱 |
| VPN 服务 | $3-12/月 | 中等 | 中等 | 高 | 数十服务器 | 中等 |
| 自建代理服务器 | $5-50/月 | 取决于IP | 快 | 高 | 1个 | 弱 |

### 各方案详解

**直接爬取 Cloudflare CDN IP**
- Cloudflare CDN IP（如 172.64.x.x、104.21.x.x）是 Anycast IP
- 无法直接作为 HTTP/SOCKS5 代理使用
- 即使扫描出在线 IP，也无法建立代理连接
- CDN IP 仅用于边缘加速，不提供代理服务

**住宅代理 / 家庭代理**
- 使用真实家庭网络 IP，反爬能力最强
- 价格昂贵，按流量计费（$5-15/GB）
- 部分服务存在合规风险
- 适合对匿名性要求极高的商业爬虫场景

**数据中心代理**
- 速度快、价格适中
- IP 容易被识别为机房 IP
- 被大型网站封禁概率较高
- 适合目标网站防护较弱的场景

**免费公共代理**
- 完全免费但质量极差
- 可用率通常低于 10%
- 速度慢、不稳定
- 存在安全风险（可能被中间人攻击）

**CFspider 优势**
- 利用 Cloudflare Workers 的边缘计算能力
- 请求从 Cloudflare 300+ 全球节点发出
- IP 是 Cloudflare 企业级 IP（与大量正常网站共用）
- 不易被封禁，且完全免费
- Workers 免费版每日 100,000 请求

## 特性

- 使用 Cloudflare 全球 300+ 边缘节点 IP
- 与 requests 库语法一致，无学习成本
- 支持 GET、POST、PUT、DELETE 等所有 HTTP 方法
- 支持 Session 会话管理
- 返回 Cloudflare 节点信息（cf_colo、cf_ray）
- **支持浏览器模式**，可渲染 JavaScript 动态页面、截图、自动化操作
- **支持多种代理方式**：HTTP 代理、SOCKS5 代理、edgetunnel VLESS 代理
- 完全免费，Workers 免费版每日 100,000 请求

## 测试结果

| 功能 | 状态 | 说明 |
|------|------|------|
| HTTP GET 请求 | OK | 返回 Cloudflare IP |
| HTTP POST 请求 | OK | 发送数据成功 |
| 自定义 Headers | OK | Header 正确传递 |
| Session 会话 | OK | 多次请求正常 |
| Workers Debug | OK | 返回 CF 机房信息 |
| 浏览器(HTTP代理) | OK | 支持本地/远程代理 |
| 浏览器(VLESS) | OK | Cloudflare IP 出口 |
| 浏览器(无代理) | OK | 本地 IP 出口 |

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

### 安装浏览器功能（可选）

如需使用浏览器模式，需要额外安装：

```bash
# 安装带浏览器支持的 cfspider
pip install cfspider[browser]

# 安装 Chromium 浏览器
cfspider install
```

## 快速开始

### HTTP 代理请求

```python
import cfspider

cf_proxies = "https://your-workers.dev"

response = cfspider.get("https://httpbin.org/ip", cf_proxies=cf_proxies)
print(response.text)
# {"origin": "2a06:98c0:3600::103, 172.71.24.151"}  # Cloudflare IP
```

### 浏览器模式

```python
import cfspider

# 使用本地 HTTP 代理
browser = cfspider.Browser(cf_proxies="127.0.0.1:9674")
html = browser.html("https://httpbin.org/ip")
print(html)
browser.close()

# 使用 edgetunnel VLESS 代理（Cloudflare IP 出口）
browser = cfspider.Browser(
    cf_proxies="v2.example.com",
    vless_uuid="your-vless-uuid"
)
html = browser.html("https://httpbin.org/ip")
print(html)  # 返回 Cloudflare IP
browser.close()

# 无代理模式
browser = cfspider.Browser()
html = browser.html("https://example.com")
browser.close()
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

## 浏览器模式

CFspider 支持浏览器模式，可以渲染 JavaScript 动态页面、截图、生成 PDF、自动化操作等。

### 安装

```bash
# 安装带浏览器支持的 cfspider
pip install cfspider[browser]

# 安装 Chromium 浏览器
cfspider install
```

### 代理类型支持

浏览器模式支持多种代理类型：

```python
import cfspider

# 1. HTTP 代理（IP:PORT 格式）
browser = cfspider.Browser(cf_proxies="127.0.0.1:9674")

# 2. HTTP 代理（完整格式）
browser = cfspider.Browser(cf_proxies="http://127.0.0.1:9674")

# 3. SOCKS5 代理
browser = cfspider.Browser(cf_proxies="socks5://127.0.0.1:1080")

# 4. edgetunnel VLESS 代理（Cloudflare IP 出口）
browser = cfspider.Browser(
    cf_proxies="v2.example.com",
    vless_uuid="your-vless-uuid"
)

# 5. 无代理
browser = cfspider.Browser()
```

### 获取渲染后的 HTML

```python
import cfspider

browser = cfspider.Browser(cf_proxies="127.0.0.1:9674")

# 获取 JavaScript 渲染后的完整 HTML
html = browser.html("https://example.com")
print(html)

browser.close()
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
result = browser.execute_script("https://example.com", "document.title")
print(result)  # Example Domain

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

## Workers API 接口

| 方法 | 接口 | 说明 |
|------|------|------|
| GET | /api/fetch?url=... | 代理请求目标 URL，返回原始内容 |
| GET | /api/json?url=... | 代理请求目标 URL，返回 JSON（含节点信息） |
| GET | /api/pool | 获取当前节点的 IP 池状态信息 |
| GET | /api/proxyip | 获取当前使用的 Proxy IP 和节点代码 |
| POST | /proxy?url=...&method=... | Python 客户端使用的代理接口 |
| GET | /debug | 调试接口，返回当前请求的详细信息 |

## 注意事项

1. Workers 免费版限制：每日 100,000 请求，单次 CPU 时间 10ms
2. 请求体大小限制：免费版 100MB，付费版无限制
3. 超时限制：免费版 30 秒，付费版无限制
4. 不支持 WebSocket、gRPC 等非 HTTP 协议
5. 浏览器模式需要额外安装 `playwright` 和 Chromium
6. edgetunnel VLESS 代理需要单独部署 edgetunnel Workers

## 致谢

本项目的浏览器 VLESS 代理功能借鉴并使用了 [edgetunnel](https://github.com/cmliu/edgetunnel) 项目。

edgetunnel 是一个优秀的 Cloudflare Workers VLESS 代理实现，感谢 [@cmliu](https://github.com/cmliu) 的开源贡献。

如需使用浏览器模式的 Cloudflare IP 出口功能，请先部署 edgetunnel Workers：
- 仓库地址：https://github.com/cmliu/edgetunnel

## License

MIT License

## 链接

- GitHub: https://github.com/violettoolssite/CFspider
- PyPI: https://pypi.org/project/cfspider/
- 官网: https://spider.violetteam.cloud
- edgetunnel: https://github.com/cmliu/edgetunnel
