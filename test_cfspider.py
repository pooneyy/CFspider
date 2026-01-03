"""
CFspider 完整功能测试
"""
import cfspider

print("=" * 60)
print("CFspider 完整功能测试")
print("=" * 60)

# 测试配置
WORKERS_URL = "https://cfspider.violetqqcom.workers.dev"
LOCAL_PROXY = "127.0.0.1:9674"
EDGETUNNEL = "v2.kami666.xyz"
VLESS_UUID = "c373c80c-58e4-4e64-8db5-40096905ec58"

# ============================================================
# 1. HTTP 请求测试（通过 Workers API）
# ============================================================
print("\n[1] HTTP 请求测试（通过 Workers API）")
print("-" * 40)

# 1.1 GET 请求
print("\n1.1 GET 请求:")
try:
    response = cfspider.get("https://httpbin.org/ip", cf_proxies=WORKERS_URL)
    print(f"  状态码: {response.status_code}")
    print(f"  响应: {response.text.strip()}")
except Exception as e:
    print(f"  错误: {e}")

# 1.2 POST 请求
print("\n1.2 POST 请求:")
try:
    response = cfspider.post(
        "https://httpbin.org/post",
        cf_proxies=WORKERS_URL,
        json={"test": "cfspider", "version": cfspider.__version__}
    )
    print(f"  状态码: {response.status_code}")
    data = response.json()
    print(f"  发送数据: {data.get('json', {})}")
except Exception as e:
    print(f"  错误: {e}")

# 1.3 自定义 Headers
print("\n1.3 自定义 Headers:")
try:
    response = cfspider.get(
        "https://httpbin.org/headers",
        cf_proxies=WORKERS_URL,
        headers={"X-Custom-Header": "CFspider-Test"}
    )
    print(f"  状态码: {response.status_code}")
    headers = response.json().get("headers", {})
    print(f"  自定义 Header: {headers.get('X-Custom-Header', 'N/A')}")
except Exception as e:
    print(f"  错误: {e}")

# ============================================================
# 2. Session 测试
# ============================================================
print("\n[2] Session 测试")
print("-" * 40)

try:
    session = cfspider.Session(cf_proxies=WORKERS_URL)
    session.headers.update({"User-Agent": "CFspider-Session-Test"})
    
    # 多次请求
    for i in range(2):
        response = session.get("https://httpbin.org/ip")
        print(f"  请求 {i+1}: {response.json().get('origin', 'N/A')}")
except Exception as e:
    print(f"  错误: {e}")

# ============================================================
# 3. Workers API 测试
# ============================================================
print("\n[3] Workers API 测试")
print("-" * 40)

# 3.1 Debug 接口
print("\n3.1 Debug 接口:")
try:
    import requests
    response = requests.get(f"{WORKERS_URL}/debug", timeout=10)
    data = response.json()
    print(f"  成功: {data.get('success')}")
    print(f"  CF 机房: {data.get('cf_colo')}")
    print(f"  ProxyIP: {data.get('proxyip')}")
except Exception as e:
    print(f"  错误: {e}")

# 3.2 IP 池接口
print("\n3.2 IP 池接口:")
try:
    import requests
    response = requests.get(f"{WORKERS_URL}/api/ips", timeout=10)
    data = response.json()
    if data.get("success"):
        ips = data.get("ips", [])
        print(f"  IP 数量: {len(ips)}")
        if ips:
            print(f"  示例 IP: {ips[0]}")
except Exception as e:
    print(f"  错误: {e}")

# ============================================================
# 4. 浏览器测试（本地代理）
# ============================================================
print("\n[4] 浏览器测试（本地代理）")
print("-" * 40)

try:
    browser = cfspider.Browser(cf_proxies=LOCAL_PROXY)
    
    # 4.1 获取 HTML
    print("\n4.1 获取 HTML:")
    html = browser.html("https://httpbin.org/ip")
    if "origin" in html:
        import re
        match = re.search(r'"origin":\s*"([^"]+)"', html)
        if match:
            print(f"  出口 IP: {match.group(1)}")
    
    # 4.2 获取截图
    print("\n4.2 截图测试:")
    screenshot = browser.screenshot("https://example.com")
    print(f"  截图大小: {len(screenshot)} bytes")
    
    # 4.3 执行 JavaScript
    print("\n4.3 JavaScript 执行:")
    result = browser.execute_script("https://example.com", "document.title")
    print(f"  页面标题: {result}")
    
    browser.close()
    print("\n  浏览器测试完成")
except Exception as e:
    print(f"  错误: {e}")

# ============================================================
# 5. 浏览器测试（edgetunnel VLESS）
# ============================================================
print("\n[5] 浏览器测试（edgetunnel VLESS）")
print("-" * 40)

try:
    browser = cfspider.Browser(cf_proxies=EDGETUNNEL, vless_uuid=VLESS_UUID)
    
    html = browser.html("https://httpbin.org/ip")
    if "origin" in html:
        import re
        match = re.search(r'"origin":\s*"([^"]+)"', html)
        if match:
            print(f"  出口 IP（Cloudflare）: {match.group(1)}")
    
    browser.close()
    print("  VLESS 代理测试完成")
except Exception as e:
    print(f"  错误: {e}")

# ============================================================
# 6. 无代理浏览器测试
# ============================================================
print("\n[6] 无代理浏览器测试")
print("-" * 40)

try:
    browser = cfspider.Browser()
    
    html = browser.html("https://httpbin.org/ip")
    if "origin" in html:
        import re
        match = re.search(r'"origin":\s*"([^"]+)"', html)
        if match:
            print(f"  本地出口 IP: {match.group(1)}")
    
    browser.close()
    print("  无代理测试完成")
except Exception as e:
    print(f"  错误: {e}")

# ============================================================
print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)

