// CFspider 根域名重定向 Workers
// 将 cfspider.com 显示提示页面，让用户点击跳转到 www.cfspider.com

export default {
    async fetch(request, env, ctx) {
        const url = new URL(request.url);
        const hostname = url.hostname;
        
        // 如果是根域名（不含 www），显示提示页面
        if (hostname === 'cfspider.com') {
            const newUrl = 'https://www.cfspider.com' + url.pathname + url.search + url.hash;
            const html = generateRedirectPage(newUrl, hostname);
            return new Response(html, {
                headers: {
                    'Content-Type': 'text/html; charset=utf-8',
                    'Cache-Control': 'no-cache, no-store, must-revalidate'
                }
            });
        }
        
        // 如果是 www 子域名或其他域名，返回 404（这个 Workers 只用于根域名重定向）
        return new Response('Not Found', { status: 404 });
    }
};

function generateRedirectPage(newUrl, hostname) {
    return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>网站跳转 - CFspider</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
            background: linear-gradient(135deg, #0a0a0f 0%, #1a1a2e 100%);
            color: #fff;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        
        .container {
            text-align: center;
            max-width: 600px;
            width: 100%;
        }
        
        .card {
            background: linear-gradient(135deg, rgba(20, 20, 30, 0.95) 0%, rgba(30, 30, 45, 0.95) 100%);
            border: 2px solid #00f5ff;
            border-radius: 20px;
            padding: 40px;
            box-shadow: 0 0 40px rgba(0, 245, 255, 0.3), 0 0 80px rgba(0, 245, 255, 0.1);
            animation: slideUp 0.5s ease-out;
        }
        
        @keyframes slideUp {
            from {
                transform: translateY(30px);
                opacity: 0;
            }
            to {
                transform: translateY(0);
                opacity: 1;
            }
        }
        
        h1 {
            font-size: 32px;
            color: #00f5ff;
            margin-bottom: 20px;
            text-shadow: 0 0 20px rgba(0, 245, 255, 0.5);
        }
        
        p {
            font-size: 16px;
            line-height: 1.8;
            color: #e0e0e0;
            margin-bottom: 15px;
        }
        
        .domain-info {
            margin: 30px 0;
            padding: 20px;
            background: rgba(0, 245, 255, 0.1);
            border-radius: 10px;
            border: 1px solid rgba(0, 245, 255, 0.3);
        }
        
        .old-domain {
            color: #ff2d95;
            font-weight: bold;
            font-size: 18px;
        }
        
        .arrow {
            color: #00f5ff;
            font-size: 24px;
            margin: 10px 0;
        }
        
        .new-domain {
            color: #50fa7b;
            font-weight: bold;
            font-size: 18px;
        }
        
        .redirect-button {
            display: inline-block;
            margin-top: 30px;
            padding: 15px 40px;
            background: linear-gradient(135deg, #00f5ff 0%, #bd93f9 100%);
            color: #0a0a0f;
            font-size: 18px;
            font-weight: bold;
            text-decoration: none;
            border-radius: 10px;
            border: none;
            cursor: pointer;
            transition: all 0.3s ease;
            box-shadow: 0 0 20px rgba(0, 245, 255, 0.4);
        }
        
        .redirect-button:hover {
            transform: translateY(-2px);
            box-shadow: 0 0 30px rgba(0, 245, 255, 0.6);
        }
        
        .redirect-button:active {
            transform: translateY(0);
        }
        
        .note {
            margin-top: 20px;
            font-size: 14px;
            color: #999;
        }
        
        .auto-redirect {
            margin-top: 20px;
            font-size: 14px;
            color: #666;
        }
    </style>
    <script>
        // 5秒后自动跳转
        let countdown = 5;
        const countdownElement = document.getElementById('countdown');
        const redirectUrl = '${newUrl}';
        
        function updateCountdown() {
            if (countdown > 0) {
                countdownElement.textContent = countdown;
                countdown--;
                setTimeout(updateCountdown, 1000);
            } else {
                window.location.replace(redirectUrl);
            }
        }
        
        // 页面加载后开始倒计时
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', updateCountdown);
        } else {
            updateCountdown();
        }
    </script>
</head>
<body>
    <div class="container">
        <div class="card">
            <h1>🌐 网站跳转</h1>
            <p>CFspider 网站已迁移至新域名</p>
            
            <div class="domain-info">
                <div class="old-domain">${hostname}</div>
                <div class="arrow">↓</div>
                <div class="new-domain">www.cfspider.com</div>
            </div>
            
            <p>请点击下方按钮跳转到新网站</p>
            
            <button class="redirect-button" onclick="window.location.replace('${newUrl}')">
                立即跳转到新网站 →
            </button>
            
            <div class="auto-redirect">
                <p>页面将在 <span id="countdown">5</span> 秒后自动跳转...</p>
            </div>
            
            <div class="note">
                <p>如果页面没有自动跳转，请手动点击上方按钮</p>
            </div>
        </div>
    </div>
</body>
</html>`;
}

