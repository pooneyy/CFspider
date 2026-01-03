import socket
import ssl
import struct
import uuid as uuid_module
import base64
import os
import time

host = 'v2.kami666.xyz'
port = 443
path = '/c373c80c-58e4-4e64-8db5-40096905ec58'
vless_uuid = 'c373c80c-58e4-4e64-8db5-40096905ec58'
target_host = 'httpbin.org'
target_port = 80

# 连接
sock = socket.create_connection((host, port), timeout=10)
context = ssl.create_default_context()
sock = context.wrap_socket(sock, server_hostname=host)

# WebSocket 握手
key = base64.b64encode(os.urandom(16)).decode('utf-8')
request = (
    f'GET {path} HTTP/1.1\r\n'
    f'Host: {host}\r\n'
    f'Upgrade: websocket\r\n'
    f'Connection: Upgrade\r\n'
    f'Sec-WebSocket-Key: {key}\r\n'
    f'Sec-WebSocket-Version: 13\r\n'
    f'\r\n'
)
sock.sendall(request.encode('utf-8'))
response = b''
while b'\r\n\r\n' not in response:
    response += sock.recv(1024)
print('WS handshake OK')

# 构建 VLESS 头
header = bytes([0])  # 版本
header += uuid_module.UUID(vless_uuid).bytes  # UUID
header += bytes([0])  # 附加信息长度
header += bytes([1])  # 命令 TCP
header += struct.pack('>H', target_port)  # 端口
# 域名
domain_bytes = target_host.encode('utf-8')
header += bytes([2])  # 域名类型
header += bytes([len(domain_bytes)])  # 域名长度
header += domain_bytes

# HTTP 请求
http_request = b'GET /ip HTTP/1.1\r\nHost: httpbin.org\r\nConnection: close\r\n\r\n'

# 合并 VLESS 头和 HTTP 请求
payload = header + http_request
print(f'Payload length: {len(payload)}, header: {len(header)}, request: {len(http_request)}')

# 发送 WebSocket 帧
def send_ws_frame(sock, data):
    frame = bytes([0x82])  # Binary, FIN=1
    length = len(data)
    if length <= 125:
        frame += bytes([0x80 | length])
    elif length <= 65535:
        frame += bytes([0x80 | 126])
        frame += struct.pack('>H', length)
    else:
        frame += bytes([0x80 | 127])
        frame += struct.pack('>Q', length)
    mask = os.urandom(4)
    frame += mask
    masked = bytes([data[i] ^ mask[i % 4] for i in range(len(data))])
    frame += masked
    sock.sendall(frame)
    print(f'Sent {len(frame)} bytes frame')

send_ws_frame(sock, payload)

# 接收响应
time.sleep(0.5)
sock.settimeout(2)
all_data = b''
try:
    while True:
        data = sock.recv(4096)
        if not data:
            break
        all_data += data
except socket.timeout:
    pass
except Exception as e:
    print('Error:', e)

print(f'Total received: {len(all_data)} bytes')

# 解析所有帧
offset = 0
first_frame = True
while offset < len(all_data):
    if offset + 2 > len(all_data):
        break
    opcode = all_data[offset] & 0x0F
    length = all_data[offset + 1] & 0x7F
    header_len = 2
    if length == 126:
        if offset + 4 > len(all_data):
            break
        length = struct.unpack('>H', all_data[offset + 2:offset + 4])[0]
        header_len = 4
    elif length == 127:
        if offset + 10 > len(all_data):
            break
        length = struct.unpack('>Q', all_data[offset + 2:offset + 10])[0]
        header_len = 10
    
    payload = all_data[offset + header_len:offset + header_len + length]
    
    if first_frame and len(payload) >= 2:
        # 跳过 VLESS 响应头
        addon_len = payload[1]
        payload = payload[2 + addon_len:]
        first_frame = False
    
    print(payload.decode('utf-8', errors='ignore'))
    offset += header_len + length

sock.close()

