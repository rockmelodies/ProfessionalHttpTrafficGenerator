#!/bin/bash

# suricata_rule_tester.sh

# 配置部分
RULES_DIR="/var/lib/suricata/rules"
SURICATA_CONFIG="/etc/suricata/suricata.yaml"
PCAP_DIR="/home/kali/pcap_check"
LOG_DIR="/var/log/suricata"
BACKUP_SUFFIX=".bak.$(date +%Y%m%d%H%M%S)"

# 创建必要的目录
mkdir -p "$LOG_DIR"

# 备份现有规则
echo "备份现有规则文件..."
cp "${RULES_DIR}/suricata.rules"  "${RULES_DIR}/suricata.rules${BACKUP_SUFFIX}"

# 创建新的空规则文件
echo "创建新的空规则文件..."
> "${RULES_DIR}/vul.rules"

# 检查是否有参数传入（自定义规则文件）
if [ $# -eq 1 ]; then
    echo "使用自定义规则文件: $1"
    cat "$1" >> "${RULES_DIR}/vul.rules"
else
    echo "请将规则内容粘贴到此处（Ctrl+D结束输入）："
    cat >> "${RULES_DIR}/vul.rules"
fi

# 清空之前的日志
echo "清空之前的日志文件..."
> "${LOG_DIR}/fast.log"
> "${LOG_DIR}/eve.json"

# 执行Suricata测试
echo "开始测试PCAP文件..."
if [ -d "$PCAP_DIR" ]; then
    # 测试目录中的所有PCAP文件
    for pcap in "${PCAP_DIR}"/*.pcap; do
        if [ -f "$pcap" ]; then
            echo "正在测试: $pcap"
            suricata -c "$SURICATA_CONFIG" -k none -r "$pcap"
        fi
    done
elif [ -f "$PCAP_DIR" ]; then
    # 测试单个PCAP文件
    echo "正在测试单个文件: $PCAP_DIR"
    suricata -c "$SURICATA_CONFIG" -k none -r "$PCAP_DIR"
else
    echo "错误: 未找到PCAP文件或目录: $PCAP_DIR"
    exit 1
fi

# 显示结果
# 显示结果 - 改进版本
echo -e "\n测试完成，结果如下:"
echo "================================="

# 使用jq解析eve.json（如果安装了jq）
if command -v jq &> /dev/null; then
    echo "警报统计:"
    jq -r 'select(.event_type=="alert") | .alert.signature_id + ": " + .alert.signature' \
        "${LOG_DIR}/eve.json" | sort | uniq -c | sort -nr

    echo -e "\n详细警报:"
    jq -r 'select(.event_type=="alert") | "\(.timestamp) [SID:\(.alert.signature_id)] \(.alert.signature) - \(.src_ip):\(.src_port) -> \(.dest_ip):\(.dest_port))"' \
        "${LOG_DIR}/eve.json" | head -10
else
    # 回退到grep方法
    echo "警报摘要:"
    grep '"event_type":"alert"' "${LOG_DIR}/eve.json" | head -5
fi

echo "================================="
done

# 可选: 恢复原始规则
read -p "是否恢复原始规则文件？[y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    mv "${RULES_DIR}/suricata.rules${BACKUP_SUFFIX}"  "${RULES_DIR}/vul.rules"
    echo "已恢复原始规则文件"
else
    echo "新规则已保留，原始规则备份在: ${RULES_DIR}/vul.rules${BACKUP_SUFFIX}"
fi