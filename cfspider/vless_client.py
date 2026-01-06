"""
CFspider 内置 VLESS 客户端
通过 WebSocket 连接 edgetunnel，提供本地 HTTP 代理
"""

import socket
import struct
import threading
import ssl
import time
import uuid
from urllib.parse import urlparse


class VlessClient:
    """VLESS 协议客户端"""
    
    def __init__(self, ws_url, vless_uuid=None):
        """
        初始化 VLESS 客户端
        
        Args:
            ws_url: edgetunnel WebSocket 地址，如 "wss://v2.kami666.xyz"
            vless_uuid: VLESS UUID，如不提供则自动生成
        """
        self.ws_url = ws_url
        self.vless_uuid = vless_uuid or str(uuid.uuid4())
        
        parsed = urlparse(ws_url)
        self.host = parsed.hostname
        self.port = parsed.port or (443 if parsed.scheme == 'wss' else 80)
        self.path = parsed.path or '/'
        self.use_ssl = parsed.scheme == 'wss'
    
    def _create_vless_header(self, target_host, target_port):
        """创建 VLESS 请求头"""
        # VLESS 协议版本
        header = bytes([0])
        
        # UUID (16 bytes)
        uuid_bytes = uuid.UUID(self.vless_uuid).bytes
        header += uuid_bytes
        
        # 附加信息长度
        header += bytes([0])
        
        # 命令 (1 = TCP)
        header += bytes([1])
        
        # 目标端口
        header += struct.pack('>H', target_port)
        
        # 地址类型和地址
        try:
            # 尝试解析为 IPv4
            socket.inet_aton(target_host)
            header += bytes([1])  # IPv4
            header += socket.inet_aton(target_host)
        except socket.error:
            try:
                # 尝试解析为 IPv6
                socket.inet_pton(socket.AF_INET6, target_host)
                header += bytes([3])  # IPv6
                header += socket.inet_pton(socket.AF_INET6, target_host)
            except socket.error:
                # 域名
                header += bytes([2])  # 域名
                domain_bytes = target_host.encode('utf-8')
                header += bytes([len(domain_bytes)])
                header += domain_bytes
        
        return header
    
    def _websocket_handshake(self, sock):
        """执行 WebSocket 握手"""
        import base64
        import hashlib
        import os
        
        # 生成随机 key
        key = base64.b64encode(os.urandom(16)).decode('utf-8')
        
        # 构建握手请求
        request = (
            f"GET {self.path} HTTP/1.1\r\n"
            f"Host: {self.host}\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n"
            f"\r\n"
        )
        
        sock.sendall(request.encode('utf-8'))
        
        # 读取响应
        response = b''
        while b'\r\n\r\n' not in response:
            chunk = sock.recv(1024)
            if not chunk:
                raise Exception("WebSocket 握手失败")
            response += chunk
        
        if b'101' not in response:
            raise Exception(f"WebSocket 握手失败: {response.decode('utf-8', errors='ignore')}")
        
        return True
    
    def _send_ws_frame(self, sock, data):
        """发送 WebSocket 帧"""
        import os
        
        # 构建帧头
        frame = bytes([0x82])  # Binary frame, FIN=1
        
        length = len(data)
        if length <= 125:
            frame += bytes([0x80 | length])  # Masked
        elif length <= 65535:
            frame += bytes([0x80 | 126])
            frame += struct.pack('>H', length)
        else:
            frame += bytes([0x80 | 127])
            frame += struct.pack('>Q', length)
        
        # 掩码
        mask = os.urandom(4)
        frame += mask
        
        # 掩码数据
        masked_data = bytes([data[i] ^ mask[i % 4] for i in range(len(data))])
        frame += masked_data
        
        sock.sendall(frame)
    
    def _recv_ws_frame(self, sock):
        """接收 WebSocket 帧"""
        # 读取帧头
        header = sock.recv(2)
        if len(header) < 2:
            return None
        
        opcode = header[0] & 0x0F
        masked = (header[1] & 0x80) != 0
        length = header[1] & 0x7F
        
        if length == 126:
            length_bytes = sock.recv(2)
            length = struct.unpack('>H', length_bytes)[0]
        elif length == 127:
            length_bytes = sock.recv(8)
            length = struct.unpack('>Q', length_bytes)[0]
        
        if masked:
            mask = sock.recv(4)
        
        # 读取数据
        data = b''
        while len(data) < length:
            chunk = sock.recv(length - len(data))
            if not chunk:
                break
            data += chunk
        
        if masked:
            data = bytes([data[i] ^ mask[i % 4] for i in range(len(data))])
        
        # 处理关闭帧
        if opcode == 0x08:
            return None
        
        return data
    
    def connect(self, target_host, target_port):
        """
        通过 VLESS 连接到目标
        
        Returns:
            VlessConnection: 可用于读写的连接对象
        """
        # 创建连接
        sock = socket.create_connection((self.host, self.port), timeout=30)
        
        if self.use_ssl:
            context = ssl.create_default_context()
            sock = context.wrap_socket(sock, server_hostname=self.host)
        
        # WebSocket 握手
        self._websocket_handshake(sock)
        
        # 创建 VLESS 头（稍后与第一个数据包一起发送）
        vless_header = self._create_vless_header(target_host, target_port)
        
        return VlessConnection(sock, self, vless_header)


class VlessConnection:
    """VLESS 连接封装"""
    
    def __init__(self, sock, client, vless_header=None):
        self.sock = sock
        self.client = client
        self.buffer = b''
        self.first_response = True
        self.vless_header = vless_header  # 第一次发送时需要带上
        self.first_send = True
    
    def send(self, data):
        """发送数据"""
        if self.first_send and self.vless_header:
            # 第一次发送时，将 VLESS 头和数据一起发送
            self.client._send_ws_frame(self.sock, self.vless_header + data)
            self.first_send = False
        else:
            self.client._send_ws_frame(self.sock, data)
    
    def recv(self, size):
        """接收数据"""
        # 如果缓冲区不够，尝试接收更多数据
        if len(self.buffer) < size:
            try:
                frame = self.client._recv_ws_frame(self.sock)
                if frame:
                    # 第一个响应需要跳过 VLESS 响应头
                    if self.first_response and len(frame) >= 2:
                        addon_len = frame[1] if len(frame) > 1 else 0
                        frame = frame[2 + addon_len:]
                        self.first_response = False
                    self.buffer += frame
            except:
                pass
        
        result = self.buffer[:size]
        self.buffer = self.buffer[size:]
        return result
    
    def recv_all(self):
        """接收所有可用数据"""
        try:
            self.sock.setblocking(False)
            while True:
                try:
                    frame = self.client._recv_ws_frame(self.sock)
                    if frame is None:
                        break
                    
                    if self.first_response and len(frame) >= 2:
                        addon_len = frame[1] if len(frame) > 1 else 0
                        frame = frame[2 + addon_len:]
                        self.first_response = False
                    
                    self.buffer += frame
                except (BlockingIOError, ssl.SSLWantReadError):
                    break
        finally:
            self.sock.setblocking(True)
        
        result = self.buffer
        self.buffer = b''
        return result
    
    def close(self):
        """关闭连接"""
        try:
            self.sock.close()
        except:
            pass


class LocalVlessProxy:
    """本地 VLESS HTTP 代理服务器"""
    
    def __init__(self, ws_url, vless_uuid=None):
        """
        初始化本地代理
        
        Args:
            ws_url: edgetunnel WebSocket 地址
            vless_uuid: VLESS UUID
        """
        self.ws_url = ws_url
        self.vless_uuid = vless_uuid
        self.server = None
        self.thread = None
        self.port = None
        self.running = False
    
    def start(self):
        """启动代理服务器"""
        # 找可用端口
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind(('127.0.0.1', 0))
        self.port = self.server.getsockname()[1]
        self.server.listen(10)
        
        self.running = True
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()
        
        # 等待服务器就绪
        time.sleep(0.1)
        return self.port
    
    def _serve(self):
        """服务循环"""
        self.server.settimeout(1)
        while self.running:
            try:
                client, addr = self.server.accept()
                handler = threading.Thread(
                    target=self._handle_client,
                    args=(client,),
                    daemon=True
                )
                handler.start()
            except socket.timeout:
                continue
            except:
                break
    
    def _handle_client(self, client):
        """处理客户端连接"""
        try:
            client.settimeout(30)
            
            # 读取请求
            request = b''
            while b'\r\n\r\n' not in request:
                chunk = client.recv(4096)
                if not chunk:
                    return
                request += chunk
            
            # 解析请求
            lines = request.split(b'\r\n')
            first_line = lines[0].decode('utf-8')
            parts = first_line.split(' ')
            
            if len(parts) < 2:
                return
            
            method = parts[0]
            
            if method == 'CONNECT':
                # HTTPS 代理
                target = parts[1]
                if ':' in target:
                    host, port = target.rsplit(':', 1)
                    port = int(port)
                else:
                    host = target
                    port = 443
                
                self._handle_connect(client, host, port)
            else:
                # HTTP 代理
                url = parts[1]
                self._handle_http(client, method, url, request)
                
        except Exception as e:
            pass
        finally:
            try:
                client.close()
            except:
                pass
    
    def _handle_connect(self, client, host, port):
        """处理 HTTPS CONNECT 请求"""
        try:
            # 连接到 VLESS
            vless = VlessClient(self.ws_url, self.vless_uuid)
            conn = vless.connect(host, port)
            
            # 发送连接成功
            client.sendall(b'HTTP/1.1 200 Connection Established\r\n\r\n')
            
            # 双向转发（使用线程）
            self._relay_bidirectional(client, conn)
            
        except Exception as e:
            try:
                client.sendall(b'HTTP/1.1 502 Bad Gateway\r\n\r\n')
            except:
                pass
    
    def _handle_http(self, client, method, url, original_request):
        """处理 HTTP 请求"""
        try:
            parsed = urlparse(url)
            host = parsed.hostname
            port = parsed.port or 80
            path = parsed.path or '/'
            if parsed.query:
                path += '?' + parsed.query
            
            # 连接到 VLESS
            vless = VlessClient(self.ws_url, self.vless_uuid)
            conn = vless.connect(host, port)
            
            # 重建请求
            lines = original_request.split(b'\r\n')
            lines[0] = f'{method} {path} HTTP/1.1'.encode('utf-8')
            
            # 更新 Host 头
            new_lines = [lines[0]]
            has_host = False
            for line in lines[1:]:
                if line.lower().startswith(b'host:'):
                    new_lines.append(f'Host: {host}'.encode('utf-8'))
                    has_host = True
                elif line.lower().startswith(b'proxy-'):
                    continue
                else:
                    new_lines.append(line)
            
            if not has_host:
                new_lines.insert(1, f'Host: {host}'.encode('utf-8'))
            
            request = b'\r\n'.join(new_lines)
            conn.send(request)
            
            # 读取响应并转发
            self._relay_response(client, conn)
            
        except Exception as e:
            client.sendall(b'HTTP/1.1 502 Bad Gateway\r\n\r\n')
    
    def _relay_bidirectional(self, client, conn):
        """双向数据转发（使用线程）"""
        import threading
        
        stop_event = threading.Event()
        
        def client_to_vless():
            try:
                while not stop_event.is_set():
                    try:
                        client.settimeout(1)
                        data = client.recv(8192)
                        if data:
                            conn.send(data)
                        else:
                            break
                    except socket.timeout:
                        continue
                    except:
                        break
            finally:
                stop_event.set()
        
        def vless_to_client():
            try:
                while not stop_event.is_set():
                    try:
                        conn.sock.settimeout(1)
                        frame = self._recv_ws_frame_safe(conn)
                        if frame:
                            client.sendall(frame)
                        elif frame is None:
                            break
                    except socket.timeout:
                        continue
                    except:
                        break
            finally:
                stop_event.set()
        
        t1 = threading.Thread(target=client_to_vless, daemon=True)
        t2 = threading.Thread(target=vless_to_client, daemon=True)
        t1.start()
        t2.start()
        
        # 等待任一方向结束
        while not stop_event.is_set():
            time.sleep(0.1)
        
        conn.close()
    
    def _recv_ws_frame_safe(self, conn):
        """安全地接收 WebSocket 帧"""
        try:
            sock = conn.sock
            header = sock.recv(2)
            if len(header) < 2:
                return None
            
            opcode = header[0] & 0x0F
            masked = (header[1] & 0x80) != 0
            length = header[1] & 0x7F
            
            if length == 126:
                length_bytes = sock.recv(2)
                length = struct.unpack('>H', length_bytes)[0]
            elif length == 127:
                length_bytes = sock.recv(8)
                length = struct.unpack('>Q', length_bytes)[0]
            
            if masked:
                mask = sock.recv(4)
            
            data = b''
            while len(data) < length:
                chunk = sock.recv(min(length - len(data), 8192))
                if not chunk:
                    break
                data += chunk
            
            if masked:
                data = bytes([data[i] ^ mask[i % 4] for i in range(len(data))])
            
            if opcode == 0x08:
                return None
            
            # 跳过 VLESS 响应头
            if conn.first_response and len(data) >= 2:
                addon_len = data[1]
                data = data[2 + addon_len:]
                conn.first_response = False
            
            return data
        except:
            return b''
    
    def _relay_response(self, client, conn):
        """转发 HTTP 响应"""
        try:
            # 读取响应
            response = b''
            while True:
                data = conn.recv(8192)
                if not data:
                    break
                response += data
                client.sendall(data)
                
                # 检查是否完成
                if b'\r\n\r\n' in response:
                    # 简单处理：继续读取直到没有数据
                    conn.sock.settimeout(0.5)
                    try:
                        while True:
                            data = conn.recv(8192)
                            if not data:
                                break
                            client.sendall(data)
                    except socket.timeout:
                        pass
                    break
        finally:
            conn.close()
    
    def stop(self):
        """停止代理服务器"""
        self.running = False
        if self.server:
            try:
                self.server.close()
            except:
                pass
        self.server = None
        self.thread = None
        self.port = None
    
    @property
    def proxy_url(self):
        """获取代理 URL"""
        if self.port:
            return f"http://127.0.0.1:{self.port}"
        return None

