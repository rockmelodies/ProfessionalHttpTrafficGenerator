#!/usr/bin/env python
# encoding: utf-8
# @author: rockmelodies
# @license: (C) Copyright 2013-2024, 360 Corporation Limited.
# @contact: rockysocket@gmail.com
# @software: garner
# @file: run.py
# @time: 2025/8/22 22:12
# @desc: 增强版HTTP流量包生成器，支持文件加载和多请求

import sys
import random
import os
import json
from datetime import datetime
from scapy.all import Ether, IP, TCP, Raw, wrpcap
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QTextEdit, QPushButton, QLabel,
                             QFileDialog, QMessageBox, QTabWidget, QGroupBox,
                             QGridLayout, QComboBox, QLineEdit, QCheckBox,
                             QProgressBar, QSplitter, QListWidget, QListWidgetItem,
                             QStackedWidget, QToolButton, QMenu, QSizePolicy)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QObject, QSize
from PyQt6.QtGui import QFont, QPalette, QColor, QTextCursor, QIcon, QAction


class HTTPRequestProcessor:
    """HTTP请求处理器，负责格式化和验证"""

    @staticmethod
    def format_http_content(content_text, is_request=True):
        """
        格式化HTTP内容，确保使用正确的行分隔符和Content-Length
        """
        if not content_text.strip():
            return content_text

        # 确保使用 \r\n 作为行分隔符
        lines = content_text.replace('\r\n', '\n').replace('\r', '\n').split('\n')

        # 分离头部和体部
        header_end_index = -1
        for i, line in enumerate(lines):
            if line.strip() == '':
                header_end_index = i
                break

        if header_end_index == -1:
            headers = lines
            body_lines = []
        else:
            headers = lines[:header_end_index]
            body_lines = lines[header_end_index + 1:]

        # 处理起始行（请求行或状态行）
        if headers and headers[0].strip():
            start_line = headers[0].strip()
        else:
            start_line = "GET / HTTP/1.1" if is_request else "HTTP/1.1 200 OK"

        # 处理头部
        processed_headers = []
        has_content_length = False
        content_length_value = 0

        for header in headers[1:]:
            if header.strip():
                if ':' in header:
                    key, value = header.split(':', 1)
                    key = key.strip()
                    value = value.strip()

                    if key.lower() == 'content-length':
                        has_content_length = True
                        try:
                            content_length_value = int(value)
                        except ValueError:
                            content_length_value = 0

                    processed_headers.append(f"{key}: {value}")

        # 计算体部长度
        body_text = '\n'.join(body_lines)
        actual_body_length = len(body_text.encode('utf-8'))

        # 自动添加或更新Content-Length
        if actual_body_length > 0:
            if not has_content_length:
                processed_headers.append(f"Content-Length: {actual_body_length}")
            else:
                # 更新现有的Content-Length
                processed_headers = [
                    header for header in processed_headers
                    if not header.lower().startswith('content-length:')
                ]
                processed_headers.append(f"Content-Length: {actual_body_length}")

        # 确保必要的头部存在（仅对请求）
        if is_request and not any(header.lower().startswith('host:') for header in processed_headers):
            host = "example.com"
            if '//' in start_line:
                url_part = start_line.split()[1] if len(start_line.split()) > 1 else ''
                if '//' in url_part:
                    host = url_part.split('//')[1].split('/')[0]
                elif url_part:
                    host = url_part.split('/')[0]
            processed_headers.append(f"Host: {host}")

        # 重新构建内容，使用 \r\n 分隔
        formatted_content = start_line + '\r\n'
        formatted_content += '\r\n'.join(processed_headers)

        if body_text:
            formatted_content += '\r\n\r\n' + body_text
        else:
            formatted_content += '\r\n\r\n'

        return formatted_content

    @staticmethod
    def validate_http_request(request_text):
        """
        验证HTTP请求格式
        """
        if not request_text.strip():
            return False, "请求内容为空"

        lines = request_text.replace('\r\n', '\n').split('\n')
        if not lines:
            return False, "无效的请求格式"

        # 检查请求行
        request_line = lines[0].strip()
        if not request_line:
            return False, "缺少请求行"

        parts = request_line.split()
        if len(parts) < 3:
            return False, "请求行格式不正确，应为: METHOD PATH HTTP/VERSION"

        method, path, version = parts[0], parts[1], parts[2]
        if not method.isupper():
            return False, "HTTP方法必须大写"

        if not version.startswith('HTTP/'):
            return False, "HTTP版本格式不正确"

        return True, "请求格式正确"


class TrafficGeneratorWorker(QObject):
    """流量生成工作线程"""
    progress_signal = pyqtSignal(int, str)
    finished_signal = pyqtSignal(str, list)
    error_signal = pyqtSignal(str)

    def __init__(self, config, requests_data):
        super().__init__()
        self.config = config
        self.requests_data = requests_data
        self.is_cancelled = False
        self.http_processor = HTTPRequestProcessor()

    def cancel(self):
        """取消生成"""
        self.is_cancelled = True

    def generate_traffic(self):
        """生成流量包的主方法"""
        try:
            packets = []
            details = []
            total_requests = len(self.requests_data)

            if total_requests == 0:
                self.error_signal.emit("没有可用的HTTP请求数据")
                return

            total_steps = self.calculate_total_steps(total_requests)
            current_step = 0

            # 初始化序列号
            client_isn = self.config['client_isn']
            server_isn = self.config['server_isn']

            for request_idx, request_data in enumerate(self.requests_data):
                if self.is_cancelled:
                    break

                # 格式化HTTP请求和响应
                raw_request_text = request_data['request']
                raw_response_text = request_data.get('response', '')

                # 格式化请求
                formatted_request = self.http_processor.format_http_content(raw_request_text, is_request=True)
                is_valid, validation_msg = self.http_processor.validate_http_request(formatted_request)

                if not is_valid:
                    self.error_signal.emit(f"请求{request_idx + 1}格式错误: {validation_msg}")
                    return

                # 格式化响应（如果有）
                formatted_response = ""
                if raw_response_text:
                    formatted_response = self.http_processor.format_http_content(raw_response_text, is_request=False)

                request_name = request_data.get('name', f'请求{request_idx + 1}')

                details.append(f"\n🔗 {request_name}")
                details.append("=" * 50)

                # TCP三次握手
                if self.config['include_handshake'] and not self.is_cancelled:
                    details.extend([
                        f"🔄 TCP三次握手 ({request_name})",
                        f"   SYN: {self.config['src_ip']}:{self.config['src_port']} → "
                        f"{self.config['dst_ip']}:{self.config['dst_port']} (seq={client_isn})",
                        f"   SYN-ACK: {self.config['dst_ip']}:{self.config['dst_port']} → "
                        f"{self.config['src_ip']}:{self.config['src_port']} "
                        f"(seq={server_isn}, ack={client_isn + 1})",
                        f"   ACK: {self.config['src_ip']}:{self.config['src_port']} → "
                        f"{self.config['dst_ip']}:{self.config['dst_port']} "
                        f"(seq={client_isn + 1}, ack={server_isn + 1})",
                        ""
                    ])

                    # 添加握手包
                    packets.extend([
                        Ether(src=self.config['src_mac'], dst=self.config['dst_mac']) /
                        IP(src=self.config['src_ip'], dst=self.config['dst_ip']) /
                        TCP(sport=self.config['src_port'], dport=self.config['dst_port'],
                            flags="S", seq=client_isn),

                        Ether(src=self.config['dst_mac'], dst=self.config['src_mac']) /
                        IP(src=self.config['dst_ip'], dst=self.config['src_ip']) /
                        TCP(sport=self.config['dst_port'], dport=self.config['src_port'],
                            flags="SA", seq=server_isn, ack=client_isn + 1),

                        Ether(src=self.config['src_mac'], dst=self.config['dst_mac']) /
                        IP(src=self.config['src_ip'], dst=self.config['dst_ip']) /
                        TCP(sport=self.config['src_port'], dport=self.config['dst_port'],
                            flags="A", seq=client_isn + 1, ack=server_isn + 1)
                    ])

                    current_step += 3
                    progress = int((current_step / total_steps) * 100)
                    self.progress_signal.emit(progress, f"TCP握手完成 ({request_name})")

                # HTTP请求和响应
                if self.config['include_http'] and not self.is_cancelled:
                    # HTTP请求
                    http_request_len = len(formatted_request.encode('utf-8'))
                    details.extend([
                        f"📨 HTTP请求 ({request_name})",
                        f"   长度: {http_request_len} 字节",
                        f"   方法: {formatted_request.split()[0]}",
                        f"   路径: {formatted_request.split()[1]}",
                        f"   内容长度: {self.extract_content_length(formatted_request)} 字节",
                        ""
                    ])

                    # 分块处理大请求
                    chunk_size = 1460
                    request_bytes = formatted_request.encode('utf-8')
                    request_chunks = self.chunk_data(request_bytes, chunk_size)

                    seq = client_isn + 1
                    for i, chunk in enumerate(request_chunks):
                        if self.is_cancelled:
                            break

                        flags = "PA" if i == len(request_chunks) - 1 else "A"
                        packets.append(
                            Ether(src=self.config['src_mac'], dst=self.config['dst_mac']) /
                            IP(src=self.config['src_ip'], dst=self.config['dst_ip']) /
                            TCP(sport=self.config['src_port'], dport=self.config['dst_port'],
                                flags=flags, seq=seq, ack=server_isn + 1) /
                            Raw(load=chunk)
                        )
                        seq += len(chunk)

                    # 服务器确认
                    packets.append(
                        Ether(src=self.config['dst_mac'], dst=self.config['src_mac']) /
                        IP(src=self.config['dst_ip'], dst=self.config['src_ip']) /
                        TCP(sport=self.config['dst_port'], dport=self.config['src_port'],
                            flags="A", seq=server_isn + 1, ack=seq)
                    )

                    current_step += 1
                    progress = int((current_step / total_steps) * 100)
                    self.progress_signal.emit(progress, f"请求发送完成 ({request_name})")

                    # HTTP响应
                    if formatted_response and not self.is_cancelled:
                        http_response_len = len(formatted_response.encode('utf-8'))
                        details.extend([
                            f"📩 HTTP响应 ({request_name})",
                            f"   长度: {http_response_len} 字节",
                            f"   状态码: {self.extract_status_code(formatted_response)}",
                            f"   内容长度: {self.extract_content_length(formatted_response)} 字节",
                            ""
                        ])

                        # 分块处理大响应
                        response_bytes = formatted_response.encode('utf-8')
                        response_chunks = self.chunk_data(response_bytes, chunk_size)

                        resp_seq = server_isn + 1
                        for i, chunk in enumerate(response_chunks):
                            if self.is_cancelled:
                                break

                            flags = "PA" if i == len(response_chunks) - 1 else "A"
                            packets.append(
                                Ether(src=self.config['dst_mac'], dst=self.config['src_mac']) /
                                IP(src=self.config['dst_ip'], dst=self.config['src_ip']) /
                                TCP(sport=self.config['dst_port'], dport=self.config['src_port'],
                                    flags=flags, seq=resp_seq, ack=seq) /
                                Raw(load=chunk)
                            )
                            resp_seq += len(chunk)

                        # 客户端确认
                        packets.append(
                            Ether(src=self.config['src_mac'], dst=self.config['dst_mac']) /
                            IP(src=self.config['src_ip'], dst=self.config['dst_ip']) /
                            TCP(sport=self.config['src_port'], dport=self.config['dst_port'],
                                flags="A", seq=seq, ack=resp_seq)
                        )

                        current_step += 1
                        progress = int((current_step / total_steps) * 100)
                        self.progress_signal.emit(progress, f"响应发送完成 ({request_name})")

                # TCP四次挥手
                if self.config['include_teardown'] and not self.is_cancelled:
                    details.extend([
                        f"🔄 TCP四次挥手 ({request_name})",
                        f"   FIN-ACK: {self.config['src_ip']}:{self.config['src_port']} → "
                        f"{self.config['dst_ip']}:{self.config['dst_port']}",
                        f"   ACK: {self.config['dst_ip']}:{self.config['dst_port']} → "
                        f"{self.config['src_ip']}:{self.config['src_port']}",
                        f"   FIN-ACK: {self.config['dst_ip']}:{self.config['dst_port']} → "
                        f"{self.config['src_ip']}:{self.config['src_port']}",
                        f"   ACK: {self.config['src_ip']}:{self.config['src_port']} → "
                        f"{self.config['dst_ip']}:{self.config['dst_port']}",
                        ""
                    ])

                    # 添加挥手包
                    packets.extend([
                        Ether(src=self.config['src_mac'], dst=self.config['dst_mac']) /
                        IP(src=self.config['src_ip'], dst=self.config['dst_ip']) /
                        TCP(sport=self.config['src_port'], dport=self.config['dst_port'],
                            flags="FA", seq=seq, ack=resp_seq),

                        Ether(src=self.config['dst_mac'], dst=self.config['src_mac']) /
                        IP(src=self.config['dst_ip'], dst=self.config['src_ip']) /
                        TCP(sport=self.config['dst_port'], dport=self.config['src_port'],
                            flags="A", seq=resp_seq, ack=seq + 1),

                        Ether(src=self.config['dst_mac'], dst=self.config['src_mac']) /
                        IP(src=self.config['dst_ip'], dst=self.config['src_ip']) /
                        TCP(sport=self.config['dst_port'], dport=self.config['src_port'],
                            flags="FA", seq=resp_seq, ack=seq + 1),

                        Ether(src=self.config['src_mac'], dst=self.config['dst_mac']) /
                        IP(src=self.config['src_ip'], dst=self.config['dst_ip']) /
                        TCP(sport=self.config['src_port'], dport=self.config['dst_port'],
                            flags="A", seq=seq + 1, ack=resp_seq + 1)
                    ])

                    current_step += 4
                    progress = int((current_step / total_steps) * 100)
                    self.progress_signal.emit(progress, f"TCP挥手完成 ({request_name})")

                # 更新序列号用于下一个请求
                client_isn = seq + 1
                server_isn = resp_seq + 1

            if self.is_cancelled:
                self.progress_signal.emit(0, "操作已取消")
                return

            # 保存文件
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = f"http_traffic_{timestamp}.pcap"
            wrpcap(file_path, packets)

            details.insert(0, f"📊 流量包生成摘要")
            details.insert(1, "=" * 50)
            details.insert(2, f"总请求数: {total_requests}")
            details.insert(3, f"总数据包: {len(packets)}")
            details.insert(4, f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

            self.finished_signal.emit(file_path, details)

        except Exception as e:
            self.error_signal.emit(f"生成流量包时出错: {str(e)}")

    def extract_content_length(self, http_text):
        """提取Content-Length"""
        lines = http_text.split('\r\n')
        for line in lines:
            if line.lower().startswith('content-length:'):
                try:
                    return int(line.split(':', 1)[1].strip())
                except ValueError:
                    return 0
        return 0

    def calculate_total_steps(self, total_requests):
        """计算总步骤数"""
        steps_per_request = 0
        if self.config['include_handshake']:
            steps_per_request += 3
        if self.config['include_http']:
            steps_per_request += 2  # 请求和ACK
            if any('response' in req and req['response'] for req in self.requests_data):
                steps_per_request += 2  # 响应和ACK
        if self.config['include_teardown']:
            steps_per_request += 4

        return steps_per_request * total_requests

    def chunk_data(self, data, chunk_size):
        """将数据分块"""
        return [data[i:i + chunk_size] for i in range(0, len(data), chunk_size)]

    def extract_status_code(self, response_text):
        """提取HTTP状态码"""
        lines = response_text.split('\n')
        if lines and lines[0].startswith('HTTP/'):
            parts = lines[0].split()
            if len(parts) >= 2:
                return parts[1]
        return '未知'


class ProfessionalHttpTrafficGenerator(QMainWindow):
    def __init__(self):
        super().__init__()
        self.worker_thread = None
        self.worker = None
        self.requests_data = []  # 存储所有请求数据
        self.current_request_index = 0
        self.initUI()
        self.applyDarkTheme()

    def initUI(self):
        self.setWindowTitle('🔍 HTTP流量包生成器 - 多请求文件支持 - 自动校验请求体数据长度和合法性V20250829版 技术支持-张菩嘉')
        self.setGeometry(100, 100, 1800, 1200)

        # 中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 主布局
        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # 左侧请求列表
        left_widget = QWidget()
        left_widget.setFixedWidth(300)
        left_layout = QVBoxLayout(left_widget)

        # 请求列表标题
        requests_label = QLabel("📋 请求列表")
        requests_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        requests_label.setStyleSheet("color: #FF9800; padding: 5px;")
        left_layout.addWidget(requests_label)

        # 请求列表
        self.requests_list = QListWidget()
        self.requests_list.setStyleSheet("""
            QListWidget {
                background-color: #2B2B2B;
                color: #E0E0E0;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #444;
            }
            QListWidget::item:selected {
                background-color: #4CAF50;
                color: white;
            }
        """)
        self.requests_list.currentRowChanged.connect(self.switch_request)
        left_layout.addWidget(self.requests_list)

        # 请求操作按钮
        request_buttons_layout = QHBoxLayout()

        request_buttons = [
            ("➕", self.add_request, "添加新请求"),
            ("➖", self.remove_request, "删除当前请求"),
            ("📁", self.load_from_file, "从文件加载"),
            ("💾", self.save_to_file, "保存到文件")
        ]

        for icon, slot, tooltip in request_buttons:
            btn = QToolButton()
            btn.setText(icon)
            btn.setToolTip(tooltip)
            btn.setFixedSize(30, 30)
            btn.setStyleSheet("""
                QToolButton {
                    background-color: #333;
                    color: white;
                    border: 1px solid #555;
                    border-radius: 4px;
                    font-size: 14px;
                }
                QToolButton:hover {
                    background-color: #4CAF50;
                }
            """)
            btn.clicked.connect(slot)
            request_buttons_layout.addWidget(btn)

        left_layout.addLayout(request_buttons_layout)
        main_layout.addWidget(left_widget)

        # 右侧编辑区域
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #555;
                border-radius: 5px;
                text-align: center;
                background: #333;
                height: 20px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #FF9800, stop:1 #4CAF50);
                border-radius: 3px;
            }
        """)
        right_layout.addWidget(self.progress_bar)

        # 状态标签
        self.status_label = QLabel("✅ 准备就绪 - 请添加HTTP请求")
        self.status_label.setStyleSheet("color: #E0E0E0; padding: 5px;")
        right_layout.addWidget(self.status_label)

        # 配置面板
        config_group = QGroupBox("⚙️ 网络配置")
        config_group.setStyleSheet("QGroupBox { font-weight: bold; color: #FF9800; }")
        config_layout = QGridLayout(config_group)
        config_layout.setSpacing(10)

        # 网络配置控件
        configs = [
            ("源IP:", "src_ip", "192.168.1.100"),
            ("目标IP:", "dst_ip", "93.184.216.34"),
            ("源端口:", "src_port", ""),
            ("目标端口:", "dst_port", "80"),
            ("源MAC:", "src_mac", "00:11:22:33:44:55"),
            ("目标MAC:", "dst_mac", "00:AA:BB:CC:DD:EE")
        ]

        for i, (label_text, attr_name, placeholder) in enumerate(configs):
            row, col = i // 2, (i % 2) * 2
            config_layout.addWidget(QLabel(label_text), row, col)
            edit = QLineEdit(placeholder)
            edit.setPlaceholderText(placeholder if placeholder else "随机")
            setattr(self, attr_name, edit)
            config_layout.addWidget(edit, row, col + 1)

        # 攻击类型选择
        config_layout.addWidget(QLabel("攻击类型:"), 3, 0)
        self.attack_type = QComboBox()
        self.attack_type.addItems(["正常流量", "SQL注入", "XSS攻击", "目录遍历", "命令注入"])
        config_layout.addWidget(self.attack_type, 3, 1)

        # 选项
        options = [
            ("TCP三次握手", "include_handshake", True),
            ("TCP四次挥手", "include_teardown", True),
            ("包含HTTP业务", "include_http", True)
        ]

        for i, (text, attr_name, checked) in enumerate(options):
            checkbox = QCheckBox(text)
            checkbox.setChecked(checked)
            setattr(self, attr_name, checkbox)
            config_layout.addWidget(checkbox, 4, i)

        right_layout.addWidget(config_group)

        # 请求名称编辑
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("请求名称:"))
        self.request_name_edit = QLineEdit()
        self.request_name_edit.setPlaceholderText("输入请求名称")
        self.request_name_edit.textChanged.connect(self.update_request_name)
        name_layout.addWidget(self.request_name_edit)
        right_layout.addLayout(name_layout)

        # 分割器用于请求/响应编辑区域
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # HTTP请求编辑区域
        request_widget = QWidget()
        request_layout = QVBoxLayout(request_widget)

        request_header_layout = QHBoxLayout()
        request_label = QLabel("📨 HTTP请求内容")
        request_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        request_label.setStyleSheet("color: #2196F3;")
        request_header_layout.addWidget(request_label)

        # 请求文件操作按钮
        self.request_file_btn = QToolButton()
        self.request_file_btn.setText("📁")
        self.request_file_btn.setToolTip("从文件加载请求")
        self.request_file_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        request_menu = QMenu(self)
        request_menu.addAction("从文件加载请求", self.load_request_from_file)
        request_menu.addAction("保存请求到文件", self.save_request_to_file)
        request_menu.addAction("清空请求内容", self.clear_request_content)
        self.request_file_btn.setMenu(request_menu)
        request_header_layout.addWidget(self.request_file_btn)
        request_header_layout.addStretch()

        request_layout.addLayout(request_header_layout)

        self.request_edit = QTextEdit()
        self.request_edit.setStyleSheet(self.get_textedit_style())
        self.request_edit.textChanged.connect(self.update_request_content)
        request_layout.addWidget(self.request_edit)

        # HTTP响应编辑区域
        response_widget = QWidget()
        response_layout = QVBoxLayout(response_widget)

        response_header_layout = QHBoxLayout()
        response_label = QLabel("📩 HTTP响应内容")
        response_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        response_label.setStyleSheet("color: #FF5722;")
        response_header_layout.addWidget(response_label)

        # 响应文件操作按钮
        self.response_file_btn = QToolButton()
        self.response_file_btn.setText("📁")
        self.response_file_btn.setToolTip("从文件加载响应")
        self.response_file_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        response_menu = QMenu(self)
        response_menu.addAction("从文件加载响应", self.load_response_from_file)
        response_menu.addAction("保存响应到文件", self.save_response_to_file)
        response_menu.addAction("清空响应内容", self.clear_response_content)
        self.response_file_btn.setMenu(response_menu)
        response_header_layout.addWidget(self.response_file_btn)
        response_header_layout.addStretch()

        response_layout.addLayout(response_header_layout)

        self.response_edit = QTextEdit()
        self.response_edit.setStyleSheet(self.get_textedit_style())
        self.response_edit.textChanged.connect(self.update_response_content)
        response_layout.addWidget(self.response_edit)

        splitter.addWidget(request_widget)
        splitter.addWidget(response_widget)
        splitter.setSizes([400, 400])
        right_layout.addWidget(splitter, 1)

        # 流量详情
        details_group = QGroupBox("📊 流量包详情")
        details_group.setStyleSheet("QGroupBox { font-weight: bold; color: #9C27B0; }")
        details_layout = QVBoxLayout(details_group)
        self.details_edit = QTextEdit()
        self.details_edit.setReadOnly(True)
        self.details_edit.setStyleSheet("""
            QTextEdit {
                background-color: #1E1E1E;
                color: #CCCCCC;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 8px;
                font-family: 'Consolas', monospace;
                min-height: 150px;
            }
        """)
        details_layout.addWidget(self.details_edit)
        right_layout.addWidget(details_group)

        # 按钮区域
        button_layout = QHBoxLayout()

        buttons = [
            ("🔄 生成示例", self.generate_example, "#FF9800"),
            ("🔍 解析内容", self.parse_content, "#2196F3"),
            ("⚡ 生成流量包", self.start_generation, "#4CAF50"),
            ("⏹️ 取消生成", self.cancel_generation, "#F44336")
        ]

        for text, slot, color in buttons:
            btn = QPushButton(text)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color};
                    color: white;
                    border: none;
                    padding: 12px 20px;
                    border-radius: 6px;
                    font-weight: bold;
                    font-size: 14px;
                    margin: 5px;
                }}
                QPushButton:hover {{
                    background-color: {self.lighten_color(color)};
                }}
                QPushButton:pressed {{
                    background-color: {self.darken_color(color)};
                }}
                QPushButton:disabled {{
                    background-color: #666;
                    color: #999;
                }}
            """)
            btn.clicked.connect(slot)
            setattr(self, f"btn_{text.split()[1]}", btn)
            button_layout.addWidget(btn)

        right_layout.addLayout(button_layout)
        main_layout.addWidget(right_widget, 1)

        # 初始化第一个请求
        self.add_request()
        self.generate_example()

    def format_current_request(self):
        """格式化当前请求和响应"""
        if 0 <= self.current_request_index < len(self.requests_data):
            # 格式化请求
            request_text = self.request_edit.toPlainText()
            formatted_request = HTTPRequestProcessor.format_http_content(request_text, is_request=True)

            # 阻塞信号避免循环触发
            self.request_edit.blockSignals(True)
            self.request_edit.setPlainText(formatted_request)
            self.requests_data[self.current_request_index]['request'] = formatted_request
            self.request_edit.blockSignals(False)

            # 格式化响应（如果有）
            response_text = self.response_edit.toPlainText()
            if response_text:
                formatted_response = HTTPRequestProcessor.format_http_content(response_text, is_request=False)

                self.response_edit.blockSignals(True)
                self.response_edit.setPlainText(formatted_response)
                self.requests_data[self.current_request_index]['response'] = formatted_response
                self.response_edit.blockSignals(False)

            self.update_status("✅ 请求和响应已格式化")

    def validate_current_request(self):
        """验证当前请求格式"""
        if 0 <= self.current_request_index < len(self.requests_data):
            request_text = self.request_edit.toPlainText()
            is_valid, message = HTTPRequestProcessor.validate_http_request(request_text)

            if is_valid:
                QMessageBox.information(self, "验证通过", "✅ HTTP请求格式正确")
            else:
                QMessageBox.warning(self, "验证失败", f"❌ {message}")

    def get_textedit_style(self):
        return """
            QTextEdit {
                background-color: #2B2B2B;
                color: #E0E0E0;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 8px;
                font-family: 'Courier New', monospace;
            }
        """

    def lighten_color(self, color):
        return color.replace("#", "#88") if len(color) == 7 else color

    def darken_color(self, color):
        return color.replace("#", "#33") if len(color) == 7 else color

    def applyDarkTheme(self):
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
        palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Base, QColor(35, 35, 35))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
        palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
        palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
        palette.setColor(QPalette.ColorRole.Highlight, QColor(142, 45, 197).lighter())
        palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
        QApplication.setPalette(palette)

    def add_request(self):
        """添加新请求"""
        new_request = {
            'name': f'请求{len(self.requests_data) + 1}',
            'request': '',
            'response': ''
        }
        self.requests_data.append(new_request)
        self.update_requests_list()
        self.requests_list.setCurrentRow(len(self.requests_data) - 1)

    def remove_request(self):
        """删除当前请求"""
        if len(self.requests_data) <= 1:
            QMessageBox.warning(self, "警告", "至少需要保留一个请求！")
            return

        current_row = self.requests_list.currentRow()
        if current_row >= 0:
            self.requests_data.pop(current_row)
            self.update_requests_list()
            self.requests_list.setCurrentRow(min(current_row, len(self.requests_data) - 1))

    def switch_request(self, index):
        """切换当前显示的请求"""
        if 0 <= index < len(self.requests_data):
            self.current_request_index = index
            request_data = self.requests_data[index]

            # 阻塞信号避免循环触发
            self.request_name_edit.blockSignals(True)
            self.request_edit.blockSignals(True)
            self.response_edit.blockSignals(True)

            self.request_name_edit.setText(request_data['name'])
            self.request_edit.setPlainText(request_data['request'])
            self.response_edit.setPlainText(request_data.get('response', ''))

            self.request_name_edit.blockSignals(False)
            self.request_edit.blockSignals(False)
            self.response_edit.blockSignals(False)

    def update_request_name(self):
        """更新请求名称"""
        if 0 <= self.current_request_index < len(self.requests_data):
            self.requests_data[self.current_request_index]['name'] = self.request_name_edit.text()
            self.update_requests_list()

    def update_request_content(self):
        """更新请求内容"""
        if 0 <= self.current_request_index < len(self.requests_data):
            self.requests_data[self.current_request_index]['request'] = self.request_edit.toPlainText()

    def update_response_content(self):
        """更新响应内容"""
        if 0 <= self.current_request_index < len(self.requests_data):
            self.requests_data[self.current_request_index]['response'] = self.response_edit.toPlainText()

    def update_requests_list(self):
        """更新请求列表显示"""
        self.requests_list.clear()
        for request in self.requests_data:
            item = QListWidgetItem(request['name'])
            # 显示请求基本信息
            request_len = len(request['request'])
            response_len = len(request.get('response', ''))
            item.setToolTip(f"请求: {request_len}字节, 响应: {response_len}字节")
            self.requests_list.addItem(item)

    def load_request_from_file(self):
        """从文件加载请求内容"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择请求文件", "", "所有文件 (*);;文本文件 (*.txt);;HTTP文件 (*.http)"
        )
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.request_edit.setPlainText(content)
                self.update_status(f"✅ 已从文件加载请求: {os.path.basename(file_path)}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"读取文件失败: {str(e)}")

    def load_response_from_file(self):
        """从文件加载响应内容"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择响应文件", "", "所有文件 (*);;文本文件 (*.txt);;HTTP文件 (*.http)"
        )
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.response_edit.setPlainText(content)
                self.update_status(f"✅ 已从文件加载响应: {os.path.basename(file_path)}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"读取文件失败: {str(e)}")

    def save_request_to_file(self):
        """保存请求内容到文件"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存请求文件", f"http_request_{datetime.now().strftime('%Y%m%d_%H%M%S')}.http",
            "HTTP文件 (*.http);;文本文件 (*.txt);;所有文件 (*)"
        )
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.request_edit.toPlainText())
                self.update_status(f"✅ 请求已保存到: {os.path.basename(file_path)}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存文件失败: {str(e)}")

    def save_response_to_file(self):
        """保存响应内容到文件"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存响应文件", f"http_response_{datetime.now().strftime('%Y%m%d_%H%M%S')}.http",
            "HTTP文件 (*.http);;文本文件 (*.txt);;所有文件 (*)"
        )
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.response_edit.toPlainText())
                self.update_status(f"✅ 响应已保存到: {os.path.basename(file_path)}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存文件失败: {str(e)}")

    def load_from_file(self):
        """从JSON文件加载所有请求"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择配置文件", "", "JSON文件 (*.json);;所有文件 (*)"
        )
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                if isinstance(data, list):
                    self.requests_data = data
                    self.update_requests_list()
                    if self.requests_data:
                        self.requests_list.setCurrentRow(0)
                    self.update_status(f"✅ 已从文件加载 {len(data)} 个请求")
                else:
                    QMessageBox.warning(self, "警告", "文件格式不正确")

            except Exception as e:
                QMessageBox.critical(self, "错误", f"读取文件失败: {str(e)}")

    def save_to_file(self):
        """保存所有请求到JSON文件"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存配置文件", f"http_requests_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "JSON文件 (*.json);;所有文件 (*)"
        )
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(self.requests_data, f, ensure_ascii=False, indent=2)
                self.update_status(f"✅ 已保存 {len(self.requests_data)} 个请求到文件")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存文件失败: {str(e)}")

    def clear_request_content(self):
        """清空请求内容"""
        self.request_edit.clear()

    def clear_response_content(self):
        """清空响应内容"""
        self.response_edit.clear()

    def generate_example(self):
        """生成示例HTTP内容"""
        attack_type = self.attack_type.currentText()

        if attack_type == "SQL注入":
            request = """POST /login.php HTTP/1.1
Host: vulnerable-site.com
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)
Content-Type: application/x-www-form-urlencoded
Content-Length: 45
Connection: keep-alive

username=admin' OR '1'='1&password=anypassword"""

            response = """HTTP/1.1 302 Found
Date: Mon, 15 Jan 2024 10:30:00 GMT
Server: Apache/2.4.41
Location: /dashboard.php
Set-Cookie: sessionid=hacked_session_12345
Content-Type: text/html
Content-Length: 0
Connection: keep-alive

"""

        elif attack_type == "XSS攻击":
            request = """GET /search?q=<script>alert('XSS')</script> HTTP/1.1
Host: xss-vulnerable.com
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)
Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8
Connection: keep-alive

"""

            response = """HTTP/1.1 200 OK
Date: Mon, 15 Jan 2024 10:30:00 GMT
Server: nginx/1.18.0
Content-Type: text/html; charset=utf-8
Content-Length: 256
Connection: keep-alive

<html>
<head><title>Search Results</title></head>
<body>
<h1>Search Results for: <script>alert('XSS')</script></h1>
<p>No results found for your query.</p>
</body>
</html>"""

        else:  # 正常流量
            request = """GET / HTTP/1.1
Host: example.com
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)
Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8
Accept-Language: en-US,en;q=0.5
Accept-Encoding: gzip, deflate
Connection: keep-alive
Upgrade-Insecure-Requests: 1

"""

            response = """HTTP/1.1 200 OK
Date: Mon, 15 Jan 2024 12:00:00 GMT
Server: Apache/2.4.41
Last-Modified: Wed, 10 Jan 2024 15:30:00 GMT
Content-Type: text/html; charset=utf-8
Content-Length: 127
Connection: keep-alive

<html>
<head><title>Example Domain</title></head>
<body>
<h1>Welcome to Example Domain</h1>
<p>This is a sample response.</p>
</body>
</html>"""

        if 0 <= self.current_request_index < len(self.requests_data):
            self.requests_data[self.current_request_index]['request'] = request
            self.requests_data[self.current_request_index]['response'] = response
            self.request_edit.setPlainText(request)
            self.response_edit.setPlainText(response)
            self.update_status(f"✅ 已生成{attack_type}示例流量")

    def parse_content(self):
        """解析HTTP内容"""
        if 0 <= self.current_request_index < len(self.requests_data):
            request_data = self.requests_data[self.current_request_index]
            request = request_data['request']
            response = request_data.get('response', '')

            details = ["📋 HTTP内容解析结果", "=" * 50]

            if request:
                details.append("\n📨 HTTP请求:")
                details.append(f"   长度: {len(request)} 字符")
                if "HTTP/" in request.split('\n')[0]:
                    details.append(f"   方法: {request.split()[0]}")
                    details.append(f"   路径: {request.split()[1]}")

            if response:
                details.append("\n📩 HTTP响应:")
                details.append(f"   长度: {len(response)} 字符")
                if response.startswith("HTTP/"):
                    details.append(f"   状态码: {response.split()[1]}")

            self.details_edit.setPlainText("\n".join(details))
            self.update_status("✅ HTTP内容解析完成")

    def start_generation(self):
        """开始生成流量包"""
        if not self.requests_data:
            QMessageBox.warning(self, "警告", "请至少添加一个HTTP请求！")
            return

        # 禁用按钮，显示进度条
        self.set_ui_enabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        # 获取配置
        config = {
            'src_ip': self.src_ip.text() or "192.168.1.100",
            'dst_ip': self.dst_ip.text() or "93.184.216.34",
            'src_port': int(self.src_port.text()) if self.src_port.text() else random.randint(1024, 65535),
            'dst_port': int(self.dst_port.text() or 80),
            'src_mac': self.src_mac.text() or "00:11:22:33:44:55",
            'dst_mac': self.dst_mac.text() or "00:AA:BB:CC:DD:EE",
            'client_isn': random.randint(1000, 100000),
            'server_isn': random.randint(1000, 100000),
            'include_handshake': self.include_handshake.isChecked(),
            'include_teardown': self.include_teardown.isChecked(),
            'include_http': self.include_http.isChecked()
        }

        # 创建工作线程
        self.worker_thread = QThread()
        self.worker = TrafficGeneratorWorker(config, self.requests_data)
        self.worker.moveToThread(self.worker_thread)

        # 连接信号
        self.worker.progress_signal.connect(self.update_progress)
        self.worker.finished_signal.connect(self.generation_finished)
        self.worker.error_signal.connect(self.generation_error)

        # 启动线程
        self.worker_thread.started.connect(self.worker.generate_traffic)
        self.worker_thread.start()

    def cancel_generation(self):
        """取消生成"""
        if self.worker:
            self.worker.cancel()
            self.update_status("⏹️ 正在取消生成...")

    def update_progress(self, value, message):
        """更新进度"""
        self.progress_bar.setValue(value)
        self.update_status(f"🔄 {message} ({value}%)")

    def generation_finished(self, file_path, details):
        """生成完成"""
        if self.worker_thread:
            self.worker_thread.quit()
            self.worker_thread.wait()

        self.set_ui_enabled(True)
        self.progress_bar.setVisible(False)

        self.details_edit.setPlainText("\n".join(details))

        QMessageBox.information(
            self, "成功",
            f"✅ 流量包生成成功！\n\n"
            f"📁 文件: {file_path}\n"
            f"📦 总请求数: {len(self.requests_data)}\n"
            f"📨 最大请求长度: {max(len(r['request']) for r in self.requests_data)} 字节"
        )

        self.update_status(f"✅ 流量包已保存: {file_path}")

    def generation_error(self, error_message):
        """生成错误"""
        if self.worker_thread:
            self.worker_thread.quit()
            self.worker_thread.wait()

        self.set_ui_enabled(True)
        self.progress_bar.setVisible(False)

        QMessageBox.critical(self, "错误", error_message)
        self.update_status("❌ 生成失败")

    def set_ui_enabled(self, enabled):
        """设置UI启用状态"""
        self.btn_生成示例.setEnabled(enabled)
        self.btn_解析内容.setEnabled(enabled)
        self.btn_生成流量包.setEnabled(enabled)
        self.btn_取消生成.setEnabled(not enabled)

    def update_status(self, message):
        """更新状态"""
        self.status_label.setText(message)

    def closeEvent(self, event):
        """关闭事件"""
        if self.worker_thread and self.worker_thread.isRunning():
            if self.worker:
                self.worker.cancel()
            self.worker_thread.quit()
            self.worker_thread.wait(2000)
        event.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = ProfessionalHttpTrafficGenerator()
    window.show()
    sys.exit(app.exec())