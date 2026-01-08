import cfspider

# ========== 方案一：使用有效的 Workers 地址 ==========
# 请将下面的地址替换为你的实际 Workers 地址
# Workers 地址格式：https://your-worker-name.your-subdomain.workers.dev
WORKERS_URL = "https://proxy.kami666.xyz/"  # 替换为你的 Workers 地址
TOKEN = "HAIfuge27"  # 替换为你在 Workers 中配置的 token

try:
    # 使用 Token 鉴权的请求
    res = cfspider.get(
        "https://httpbin.org/ip",
        cf_proxies=WORKERS_URL,
        token=TOKEN 
    )
    
    print("✅ 请求成功！")
    print(f"响应内容: {res.text}")
    print(f"节点代码: {res.cf_colo}")
    print(f"Ray ID: {res.cf_ray}")
    print(f"状态码: {res.status_code}")
    
except Exception as e:
    print(f"❌ 请求失败: {e}")
    print("\n可能的原因：")
    print("1. Workers 地址不正确或域名无法解析")
    print("2. Token 配置错误")
    print("3. 网络连接问题")
    print("\n解决方案：")
    print("1. 检查 Workers 地址是否正确")
    print("2. 确认 Workers 已部署并运行")
    print("3. 检查 Token 是否在 Workers 环境变量中配置")
    print("4. 尝试不使用代理测试（见下方方案二）")

# ========== 方案二：不使用代理测试（用于验证库是否正常）==========
print("\n" + "="*50)
print("测试：不使用代理直接请求")
try:
    res = cfspider.get("https://httpbin.org/ip")
    print("✅ 直接请求成功！")
    print(f"响应内容: {res.text}")
except Exception as e:
    print(f"❌ 直接请求也失败: {e}")