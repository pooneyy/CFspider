"""
CFspider IP 地图可视化模块

生成包含代理 IP 地理位置的 HTML 地图文件，使用 MapLibre GL JS。
"""
import json
from typing import Optional, List, Dict, Any
from datetime import datetime


# Cloudflare 节点代码对应的坐标（主要节点）
COLO_COORDINATES = {
    # 亚洲
    "NRT": {"lat": 35.6762, "lng": 139.6503, "city": "东京", "country": "日本"},
    "HND": {"lat": 35.5494, "lng": 139.7798, "city": "东京羽田", "country": "日本"},
    "KIX": {"lat": 34.4347, "lng": 135.2441, "city": "大阪", "country": "日本"},
    "HKG": {"lat": 22.3080, "lng": 113.9185, "city": "香港", "country": "香港"},
    "SIN": {"lat": 1.3521, "lng": 103.8198, "city": "新加坡", "country": "新加坡"},
    "ICN": {"lat": 37.4602, "lng": 126.4407, "city": "首尔", "country": "韩国"},
    "TPE": {"lat": 25.0777, "lng": 121.2330, "city": "台北", "country": "台湾"},
    "BKK": {"lat": 13.6900, "lng": 100.7501, "city": "曼谷", "country": "泰国"},
    "KUL": {"lat": 2.7456, "lng": 101.7072, "city": "吉隆坡", "country": "马来西亚"},
    "BOM": {"lat": 19.0896, "lng": 72.8656, "city": "孟买", "country": "印度"},
    "DEL": {"lat": 28.5562, "lng": 77.1000, "city": "新德里", "country": "印度"},
    "SYD": {"lat": -33.9399, "lng": 151.1753, "city": "悉尼", "country": "澳大利亚"},
    "MEL": {"lat": -37.6690, "lng": 144.8410, "city": "墨尔本", "country": "澳大利亚"},
    
    # 北美
    "SJC": {"lat": 37.3639, "lng": -121.9289, "city": "圣何塞", "country": "美国"},
    "LAX": {"lat": 33.9416, "lng": -118.4085, "city": "洛杉矶", "country": "美国"},
    "SEA": {"lat": 47.4502, "lng": -122.3088, "city": "西雅图", "country": "美国"},
    "DFW": {"lat": 32.8998, "lng": -97.0403, "city": "达拉斯", "country": "美国"},
    "ORD": {"lat": 41.9742, "lng": -87.9073, "city": "芝加哥", "country": "美国"},
    "IAD": {"lat": 38.9531, "lng": -77.4565, "city": "华盛顿", "country": "美国"},
    "EWR": {"lat": 40.6895, "lng": -74.1745, "city": "纽瓦克", "country": "美国"},
    "MIA": {"lat": 25.7959, "lng": -80.2870, "city": "迈阿密", "country": "美国"},
    "ATL": {"lat": 33.6407, "lng": -84.4277, "city": "亚特兰大", "country": "美国"},
    "YYZ": {"lat": 43.6777, "lng": -79.6248, "city": "多伦多", "country": "加拿大"},
    "YVR": {"lat": 49.1947, "lng": -123.1789, "city": "温哥华", "country": "加拿大"},
    
    # 欧洲
    "LHR": {"lat": 51.4700, "lng": -0.4543, "city": "伦敦", "country": "英国"},
    "CDG": {"lat": 49.0097, "lng": 2.5479, "city": "巴黎", "country": "法国"},
    "FRA": {"lat": 50.0379, "lng": 8.5622, "city": "法兰克福", "country": "德国"},
    "AMS": {"lat": 52.3105, "lng": 4.7683, "city": "阿姆斯特丹", "country": "荷兰"},
    "ZRH": {"lat": 47.4647, "lng": 8.5492, "city": "苏黎世", "country": "瑞士"},
    "MAD": {"lat": 40.4983, "lng": -3.5676, "city": "马德里", "country": "西班牙"},
    "MXP": {"lat": 45.6306, "lng": 8.7281, "city": "米兰", "country": "意大利"},
    "WAW": {"lat": 52.1672, "lng": 20.9679, "city": "华沙", "country": "波兰"},
    "ARN": {"lat": 59.6498, "lng": 17.9238, "city": "斯德哥尔摩", "country": "瑞典"},
    
    # 南美
    "GRU": {"lat": -23.4356, "lng": -46.4731, "city": "圣保罗", "country": "巴西"},
    "EZE": {"lat": -34.8222, "lng": -58.5358, "city": "布宜诺斯艾利斯", "country": "阿根廷"},
    "SCL": {"lat": -33.3930, "lng": -70.7858, "city": "圣地亚哥", "country": "智利"},
    
    # 中东/非洲
    "DXB": {"lat": 25.2532, "lng": 55.3657, "city": "迪拜", "country": "阿联酋"},
    "JNB": {"lat": -26.1392, "lng": 28.2460, "city": "约翰内斯堡", "country": "南非"},
    "CAI": {"lat": 30.1219, "lng": 31.4056, "city": "开罗", "country": "埃及"},
}


class IPMapCollector:
    """
    IP 地图数据收集器
    
    收集爬取过程中使用的代理 IP 信息，用于生成可视化地图。
    """
    
    def __init__(self):
        self.ip_records: List[Dict[str, Any]] = []
    
    def add_record(
        self,
        url: str,
        ip: Optional[str] = None,
        cf_colo: Optional[str] = None,
        cf_ray: Optional[str] = None,
        status_code: Optional[int] = None,
        response_time: Optional[float] = None
    ):
        """添加一条 IP 记录"""
        record = {
            "url": url,
            "ip": ip,
            "cf_colo": cf_colo,
            "cf_ray": cf_ray,
            "status_code": status_code,
            "response_time": response_time,
            "timestamp": datetime.now().isoformat()
        }
        
        # 获取节点坐标
        if cf_colo and cf_colo in COLO_COORDINATES:
            coord = COLO_COORDINATES[cf_colo]
            record["lat"] = coord["lat"]
            record["lng"] = coord["lng"]
            record["city"] = coord["city"]
            record["country"] = coord["country"]
        
        self.ip_records.append(record)
    
    def get_records(self) -> List[Dict[str, Any]]:
        """获取所有记录"""
        return self.ip_records
    
    def clear(self):
        """清空记录"""
        self.ip_records = []
    
    def get_unique_colos(self) -> List[str]:
        """获取唯一的节点代码列表"""
        colos = set()
        for record in self.ip_records:
            if record.get("cf_colo"):
                colos.add(record["cf_colo"])
        return list(colos)


# 全局收集器实例
_global_collector = IPMapCollector()


def get_collector() -> IPMapCollector:
    """获取全局 IP 收集器"""
    return _global_collector


def add_ip_record(
    url: str,
    ip: Optional[str] = None,
    cf_colo: Optional[str] = None,
    cf_ray: Optional[str] = None,
    status_code: Optional[int] = None,
    response_time: Optional[float] = None
):
    """添加 IP 记录到全局收集器"""
    _global_collector.add_record(
        url=url,
        ip=ip,
        cf_colo=cf_colo,
        cf_ray=cf_ray,
        status_code=status_code,
        response_time=response_time
    )


def generate_map_html(
    output_file: str = "cfspider_map.html",
    title: str = "CFspider Proxy IP Map",
    collector: Optional[IPMapCollector] = None
) -> str:
    """
    生成 IP 地图 HTML 文件
    
    Args:
        output_file: 输出文件名
        title: 页面标题
        collector: IP 收集器（默认使用全局收集器）
    
    Returns:
        生成的文件路径
    """
    if collector is None:
        collector = _global_collector
    
    records = collector.get_records()
    
    # 过滤有坐标的记录
    geo_records = [r for r in records if r.get("lat") and r.get("lng")]
    
    # 生成 GeoJSON 数据
    features = []
    for i, record in enumerate(geo_records):
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [record["lng"], record["lat"]]
            },
            "properties": {
                "id": i,
                "url": record.get("url", ""),
                "ip": record.get("ip", "N/A"),
                "cf_colo": record.get("cf_colo", "N/A"),
                "cf_ray": record.get("cf_ray", "N/A"),
                "city": record.get("city", "Unknown"),
                "country": record.get("country", "Unknown"),
                "status_code": record.get("status_code", 0),
                "response_time": record.get("response_time", 0),
                "timestamp": record.get("timestamp", "")
            }
        }
        features.append(feature)
    
    geojson = {
        "type": "FeatureCollection",
        "features": features
    }
    
    # 统计信息
    total_requests = len(records)
    geo_requests = len(geo_records)
    unique_colos = collector.get_unique_colos()
    
    html_content = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <script src="https://unpkg.com/maplibre-gl@3.6.2/dist/maplibre-gl.js"></script>
    <link href="https://unpkg.com/maplibre-gl@3.6.2/dist/maplibre-gl.css" rel="stylesheet" />
    <style>
        :root {{
            --bg-primary: #0a0a0f;
            --bg-secondary: #12121a;
            --neon-cyan: #00f5ff;
            --neon-magenta: #ff2d95;
            --neon-yellow: #f7f71c;
            --neon-green: #50fa7b;
            --text-primary: #ffffff;
            --text-secondary: #888888;
        }}
        
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        
        body {{
            font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
        }}
        
        #map {{
            position: absolute;
            top: 0;
            bottom: 0;
            width: 100%;
        }}
        
        .info-panel {{
            position: absolute;
            top: 20px;
            left: 20px;
            background: rgba(10, 10, 15, 0.95);
            border: 1px solid var(--neon-cyan);
            border-radius: 12px;
            padding: 20px;
            min-width: 280px;
            box-shadow: 0 0 30px rgba(0, 245, 255, 0.3);
            z-index: 1000;
        }}
        
        .info-panel h1 {{
            font-size: 1.4rem;
            color: var(--neon-cyan);
            margin-bottom: 15px;
            text-shadow: 0 0 10px var(--neon-cyan);
        }}
        
        .stats {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
            margin-bottom: 15px;
        }}
        
        .stat-item {{
            background: rgba(0, 245, 255, 0.1);
            border: 1px solid rgba(0, 245, 255, 0.3);
            border-radius: 8px;
            padding: 10px;
            text-align: center;
        }}
        
        .stat-value {{
            font-size: 1.5rem;
            font-weight: bold;
            color: var(--neon-cyan);
        }}
        
        .stat-label {{
            font-size: 0.75rem;
            color: var(--text-secondary);
            margin-top: 5px;
        }}
        
        .colo-list {{
            background: rgba(255, 255, 255, 0.05);
            border-radius: 8px;
            padding: 10px;
            max-height: 150px;
            overflow-y: auto;
        }}
        
        .colo-tag {{
            display: inline-block;
            background: rgba(255, 45, 149, 0.2);
            border: 1px solid var(--neon-magenta);
            color: var(--neon-magenta);
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.75rem;
            margin: 2px;
        }}
        
        .maplibregl-popup-content {{
            background: rgba(10, 10, 15, 0.95) !important;
            border: 1px solid var(--neon-cyan) !important;
            border-radius: 8px !important;
            padding: 15px !important;
            color: var(--text-primary) !important;
            box-shadow: 0 0 20px rgba(0, 245, 255, 0.3) !important;
        }}
        
        .maplibregl-popup-close-button {{
            color: var(--neon-cyan) !important;
            font-size: 20px !important;
        }}
        
        .popup-title {{
            color: var(--neon-cyan);
            font-size: 1.1rem;
            font-weight: bold;
            margin-bottom: 10px;
        }}
        
        .popup-row {{
            display: flex;
            justify-content: space-between;
            padding: 5px 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }}
        
        .popup-label {{
            color: var(--text-secondary);
        }}
        
        .popup-value {{
            color: var(--neon-green);
            font-family: monospace;
        }}
        
        .footer {{
            position: absolute;
            bottom: 20px;
            left: 20px;
            background: rgba(10, 10, 15, 0.9);
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 8px;
            padding: 10px 15px;
            font-size: 0.8rem;
            color: var(--text-secondary);
            z-index: 1000;
        }}
        
        .footer a {{
            color: var(--neon-cyan);
            text-decoration: none;
        }}
    </style>
</head>
<body>
    <div id="map"></div>
    
    <div class="info-panel">
        <h1>CFspider IP Map</h1>
        <div class="stats">
            <div class="stat-item">
                <div class="stat-value">{total_requests}</div>
                <div class="stat-label">Total Requests</div>
            </div>
            <div class="stat-item">
                <div class="stat-value">{len(unique_colos)}</div>
                <div class="stat-label">Unique Nodes</div>
            </div>
        </div>
        <div class="colo-list">
            {"".join([f'<span class="colo-tag">{colo}</span>' for colo in unique_colos]) if unique_colos else '<span style="color: #888;">No data</span>'}
        </div>
    </div>
    
    <div class="footer">
        Generated by <a href="https://github.com/violettoolssite/CFspider" target="_blank">CFspider</a> | 
        {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    </div>
    
    <script>
        const geojsonData = {json.dumps(geojson)};
        
        const map = new maplibregl.Map({{
            container: 'map',
            style: {{
                version: 8,
                sources: {{
                    'carto-dark': {{
                        type: 'raster',
                        tiles: [
                            'https://a.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}@2x.png',
                            'https://b.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}@2x.png',
                            'https://c.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}@2x.png'
                        ],
                        tileSize: 256
                    }}
                }},
                layers: [{{
                    id: 'carto-dark-layer',
                    type: 'raster',
                    source: 'carto-dark',
                    minzoom: 0,
                    maxzoom: 19
                }}]
            }},
            center: [0, 20],
            zoom: 1.5
        }});
        
        map.addControl(new maplibregl.NavigationControl());
        
        map.on('load', function() {{
            // 添加数据源
            map.addSource('proxies', {{
                type: 'geojson',
                data: geojsonData
            }});
            
            // 添加圆点图层
            map.addLayer({{
                id: 'proxy-points',
                type: 'circle',
                source: 'proxies',
                paint: {{
                    'circle-radius': 10,
                    'circle-color': '#00f5ff',
                    'circle-opacity': 0.8,
                    'circle-stroke-width': 2,
                    'circle-stroke-color': '#ff2d95'
                }}
            }});
            
            // 添加发光效果
            map.addLayer({{
                id: 'proxy-points-glow',
                type: 'circle',
                source: 'proxies',
                paint: {{
                    'circle-radius': 20,
                    'circle-color': '#00f5ff',
                    'circle-opacity': 0.2,
                    'circle-blur': 1
                }}
            }}, 'proxy-points');
            
            // 点击事件
            map.on('click', 'proxy-points', function(e) {{
                const props = e.features[0].properties;
                const coordinates = e.features[0].geometry.coordinates.slice();
                
                const popupContent = `
                    <div class="popup-title">${{props.city}}, ${{props.country}}</div>
                    <div class="popup-row">
                        <span class="popup-label">Node:</span>
                        <span class="popup-value">${{props.cf_colo}}</span>
                    </div>
                    <div class="popup-row">
                        <span class="popup-label">IP:</span>
                        <span class="popup-value">${{props.ip}}</span>
                    </div>
                    <div class="popup-row">
                        <span class="popup-label">Status:</span>
                        <span class="popup-value">${{props.status_code}}</span>
                    </div>
                    <div class="popup-row">
                        <span class="popup-label">Time:</span>
                        <span class="popup-value">${{props.response_time ? props.response_time.toFixed(2) + 'ms' : 'N/A'}}</span>
                    </div>
                    <div class="popup-row" style="border: none;">
                        <span class="popup-label">URL:</span>
                        <span class="popup-value" style="font-size: 0.7rem; word-break: break-all;">${{props.url.substring(0, 40)}}...</span>
                    </div>
                `;
                
                new maplibregl.Popup()
                    .setLngLat(coordinates)
                    .setHTML(popupContent)
                    .addTo(map);
            }});
            
            // 鼠标样式
            map.on('mouseenter', 'proxy-points', function() {{
                map.getCanvas().style.cursor = 'pointer';
            }});
            
            map.on('mouseleave', 'proxy-points', function() {{
                map.getCanvas().style.cursor = '';
            }});
            
            // 如果有数据，自动缩放到数据范围
            if (geojsonData.features.length > 0) {{
                const bounds = new maplibregl.LngLatBounds();
                geojsonData.features.forEach(feature => {{
                    bounds.extend(feature.geometry.coordinates);
                }});
                map.fitBounds(bounds, {{ padding: 50 }});
            }}
        }});
    </script>
</body>
</html>'''
    
    # 写入文件
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    return output_file


def clear_records():
    """清空全局收集器的记录"""
    _global_collector.clear()

