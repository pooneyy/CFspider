"""
测试 cfspider.get() 直接使用 impersonate 参数
"""
import sys
sys.path.insert(0, '.')

import cfspider

CF_WORKERS = "https://ip.kami666.xyz"


def test_get_impersonate():
    """测试 get() 直接使用 impersonate"""
    print("\n" + "="*60)
    print("测试 1: cfspider.get() + impersonate='chrome131'")
    print("="*60)
    
    try:
        response = cfspider.get(
            "https://tls.browserleaks.com/json",
            impersonate="chrome131"
        )
        print(f"状态码: {response.status_code}")
        data = response.json()
        print(f"JA3 Hash: {data.get('ja3_hash', 'N/A')}")
        print("✓ 测试通过")
        return True
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return False


def test_get_impersonate_workers():
    """测试 get() + impersonate + Workers 代理"""
    print("\n" + "="*60)
    print("测试 2: cfspider.get() + impersonate + cf_proxies")
    print("="*60)
    
    try:
        response = cfspider.get(
            "https://httpbin.org/ip",
            impersonate="chrome131",
            cf_proxies=CF_WORKERS
        )
        print(f"状态码: {response.status_code}")
        print(f"CF Colo: {response.cf_colo}")
        print(f"响应: {response.text}")
        print("✓ 测试通过")
        return True
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return False


def test_post_impersonate():
    """测试 post() + impersonate"""
    print("\n" + "="*60)
    print("测试 3: cfspider.post() + impersonate='safari18_0'")
    print("="*60)
    
    try:
        response = cfspider.post(
            "https://httpbin.org/post",
            impersonate="safari18_0",
            json={"test": "data"}
        )
        print(f"状态码: {response.status_code}")
        data = response.json()
        print(f"POST 数据: {data.get('json')}")
        print("✓ 测试通过")
        return True
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return False


def test_different_browsers():
    """测试不同浏览器指纹"""
    print("\n" + "="*60)
    print("测试 4: 不同浏览器指纹对比")
    print("="*60)
    
    browsers = ["chrome131", "safari18_0", "firefox133"]
    
    try:
        for browser in browsers:
            response = cfspider.get(
                "https://tls.browserleaks.com/json",
                impersonate=browser
            )
            data = response.json()
            print(f"{browser}: JA3={data.get('ja3_hash', 'N/A')[:16]}...")
        
        print("✓ 测试通过")
        return True
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return False


def main():
    print("="*60)
    print("cfspider.get() impersonate 参数测试")
    print("="*60)
    
    results = []
    
    results.append(test_get_impersonate())
    results.append(test_get_impersonate_workers())
    results.append(test_post_impersonate())
    results.append(test_different_browsers())
    
    # 结果汇总
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)
    
    tests = [
        "get() + impersonate",
        "get() + impersonate + Workers",
        "post() + impersonate",
        "不同浏览器指纹"
    ]
    
    passed = sum(results)
    failed = len(results) - passed
    
    for i, (test, result) in enumerate(zip(tests, results)):
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{i+1}. {test}: {status}")
    
    print(f"\n总计: {passed} 通过, {failed} 失败")


if __name__ == "__main__":
    main()

