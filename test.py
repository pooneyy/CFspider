import cfspider

result = cfspider.mirror(
    "https://www.apple.com",  
    save_dir="./apple_mirror",
    cf_proxies="vless://c373c80c-58e4-4e64-8db5-40096905ec58@v2.kami666.xyz:443?security=tls&type=ws&host=v2.kami666.xyz&sni=v2.kami666.xyz&path=%2F&encryption=none&allowInsecure=1#cloudflare%E8%8A%82%E7%82%B9",
    open_browser=True
)
print(f"成功: {result.success}")
print(f"失败: {result.failed_urls}")