#ProfessionalHttpTrafficGenerator


# 🌐 专业HTTP流量包生成器 - 使用指南

## 📖 项目简介

专业HTTP流量包生成器是一个基于PyQt6和Scapy开发的图形化工具，用于生成包含完整TCP握手、HTTP业务和TCP挥手的网络流量包。支持多种攻击类型的流量模拟，并生成标准的PCAP格式文件。

## 🚀 功能特性

### ✨ 核心功能
- ✅ **完整TCP通信流程**: 三次握手 + HTTP业务 + 四次挥手
- ✅ **多种攻击类型**: SQL注入、XSS攻击、目录遍历、命令注入
- ✅ **实时内容解析**: 自动解析HTTP请求和响应内容
- ✅ **自定义网络配置**: 支持自定义IP、端口、MAC地址
- ✅ **专业界面设计**: 暗色主题，现代化UI设计

### 🎨 界面特色
- 🌙 暗色主题保护眼睛
- 🎯 直观的标签页布局
- 🔄 实时状态反馈
- 📊 详细的流量包详情展示

## 📦 安装依赖

```bash
# 安装必需依赖
pip install PyQt6 scapy

# 或者使用requirements.txt
pip install -r requirements.txt
```

## 🎮 使用方法

### 1. 基本配置
1. **网络设置**: 配置源IP、目标IP、端口等信息
2. **攻击类型**: 选择需要的攻击模式或正常流量
3. **选项设置**: 选择是否包含TCP握手和挥手过程

### 2. HTTP内容编辑
```http
# 请求示例
GET /login.php HTTP/1.1
Host: example.com
User-Agent: Mozilla/5.0
Content-Type: application/x-www-form-urlencoded

username=admin&password=123456

# 响应示例  
HTTP/1.1 200 OK
Server: Apache/2.4.41
Content-Type: text/html
Content-Length: 127

<html><body>Welcome admin!</body></html>
```

### 3. 生成流量包
1. 点击"🔄 生成示例"加载示例数据
2. 点击"🔍 解析内容"验证HTTP格式
3. 点击"⚡ 生成流量包"保存PCAP文件

## 🎯 攻击类型示例

### 🔍 SQL注入攻击
```http
POST /login.php HTTP/1.1
Host: vulnerable-site.com
Content-Type: application/x-www-form-urlencoded
Content-Length: 45

username=admin' OR '1'='1&password=anypassword
```

### 🎯 XSS攻击  
```http
GET /search?q=<script>alert('XSS')</script> HTTP/1.1
Host: xss-vulnerable.com
User-Agent: Mozilla/5.0
```

### 📁 目录遍历攻击
```http
GET /../../etc/passwd HTTP/1.1
Host: vulnerable-site.com
User-Agent: Mozilla/5.0
```

## 📊 生成的流量包结构

### 🔗 TCP三次握手
```
1. SYN     客户端 → 服务器 (seq=1000)
2. SYN-ACK 服务器 → 客户端 (seq=500, ack=1001)  
3. ACK     客户端 → 服务器 (seq=1001, ack=501)
```

### 📨 HTTP业务通信
```
4. HTTP请求  客户端 → 服务器 (包含完整HTTP头和方法体)
5. ACK确认   服务器 → 客户端 (确认收到请求)
6. HTTP响应  服务器 → 客户端 (包含完整HTTP头和响应体) 
7. ACK确认   客户端 → 服务器 (确认收到响应)
```

### 🔗 TCP四次挥手
```
8. FIN-ACK 客户端 → 服务器 (请求关闭)
9. ACK     服务器 → 客户端 (确认关闭请求)
10. FIN-ACK 服务器 → 客户端 (服务器请求关闭)
11. ACK     客户端 → 服务器 (确认关闭完成)
```

## 🛠️ 技术细节

### 📋 核心组件
```python
# 主要依赖库
- PyQt6: 图形界面框架
- Scapy: 网络数据包生成和分析
- 标准库: datetime, random, sys等

# 网络层协议
- Ethernet: MAC地址处理
- IP: IP地址和路由
- TCP: 传输控制协议
- Raw: 原始HTTP数据
```

### 🔧 序列号管理
```python
# 初始化序列号
client_isn = random.randint(1000, 100000)  # 客户端初始序列号
server_isn = random.randint(1000, 100000)  # 服务器初始序列号

# 序列号递增规则
请求序列号 = client_isn + 1
确认序列号 = server_isn + 1
数据长度 = len(http_content)
```

## 📝 使用示例

### 1. 生成SQL注入流量
```python
# 选择攻击类型为"SQL注入"
# 点击"生成示例"自动填充内容
# 点击"生成流量包"保存文件
```

### 2. 分析生成的PCAP文件
```bash
# 使用Wireshark分析
wireshark sql_injection_traffic.pcap

# 使用tcpdump分析
tcpdump -r http_traffic.pcap -n
```

### 3. 自定义HTTP内容
```python
# 在请求标签页编辑自定义HTTP请求
# 在响应标签页编辑自定义HTTP响应
# 确保包含完整的HTTP协议头
```

## 🎨 界面说明

### 📋 主界面布局
```
┌─────────────────────────────────────┐
│            🌐 标题区域              │
├─────────────────────────────────────┤
│ ⚙️ 网络配置组 (IP、端口、MAC地址)   │
├─────────────────────────────────────┤
│ 📨 HTTP请求标签页                   │
│ 📩 HTTP响应标签页                   │  
│ 📊 流量详情标签页                   │
├─────────────────────────────────────┤
│ 🎯 按钮区域 (生成、解析、保存)      │
└─────────────────────────────────────┘
```

### 🎨 颜色主题
- **主色调**: #4CAF50 (绿色)
- **强调色**: #FF9800 (橙色)
- **背景色**: #2B2B2B (深灰)
- **文字色**: #FFFFFF (白色)

## 🔧 故障排除

### ❌ 常见问题
1. **依赖安装失败**
   ```bash
   # 使用国内镜像源
   pip install -i https://pypi.tuna.tsinghua.edu.cn/simple PyQt6 scapy
   ```

2. **权限问题**
   ```bash
   # Linux/Mac可能需要sudo权限
   sudo pip install PyQt6 scapy
   ```

3. **PCAP文件无法打开**
   - 确保使用最新版Wireshark
   - 检查文件格式是否正确

### ✅ 系统要求
- **Python**: 3.7+
- **操作系统**: Windows/Linux/macOS
- **内存**: 至少512MB RAM
- **磁盘空间**: 至少100MB空闲空间

## 📞 技术支持

### 🐛 提交问题
如遇问题，请提供：
1. 操作系统版本
2. Python版本
3. 错误信息截图
4. 复现步骤

### 💡 使用建议
1. 首次使用建议点击"生成示例"
2. 生成前先点击"解析内容"验证格式
3. 保存PCAP文件前确认路径可写

## 📜 许可证

本项目采用MIT许可证，允许自由使用和修改。

## 🤝 贡献指南

欢迎提交Issue和Pull Request来改进这个工具！

---

**🎉 享受使用专业HTTP流量包生成器！**