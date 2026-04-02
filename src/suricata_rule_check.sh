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
if [ -f "${RULES_DIR}/suricata.rules" ]; then
    cp "${RULES_DIR}/suricata.rules" "${RULES_DIR}/suricata.rules${BACKUP_SUFFIX}"
fi

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
> "${LOG_DIR}/eve.json" 2>/dev/null || true

# 执行Suricata测试
echo "开始测试PCAP文件..."
if [ -d "$PCAP_DIR" ]; then
    # 测试目录中的所有PCAP文件
    for pcap in "${PCAP_DIR}"/*.pcap; do
        if [ -f "$pcap" ]; then
            echo "正在测试: $pcap"
            suricata -c "$SURICATA_CONFIG" -k none -r "$pcap" -l "$LOG_DIR"
        fi
    done
elif [ -f "$PCAP_DIR" ]; then
    # 测试单个PCAP文件
    echo "正在测试单个文件: $PCAP_DIR"
    suricata -c "$SURICATA_CONFIG" -k none -r "$PCAP_DIR" -l "$LOG_DIR"
else
    echo "错误: 未找到PCAP文件或目录: $PCAP_DIR"
    exit 1
fi

# 显示结果 - 检查fast.log
echo -e "\n测试完成，结果如下:"
echo "================================="

if [ -s "${LOG_DIR}/fast.log" ]; then
    alert_count=$(wc -l < "${LOG_DIR}/fast.log")
    echo "发现 $alert_count 个警报:"
    echo "================================="

    # 显示前3条警报
    head -3 "${LOG_DIR}/fast.log"
    echo "---------------------------------"

    if [ "$alert_count" -gt 3 ]; then
        echo "...(还有更多匹配，共 $alert_count 个)"
        echo "---------------------------------"
    fi

    # 显示SID统计
    echo "SID命中统计:"
    grep -o '\[[0-9]*:[0-9]*:[0-9]*\]' "${LOG_DIR}/fast.log" | sort | uniq -c | sort -nr

else
    echo "未生成任何警报"
    echo "检查fast.log文件: ${LOG_DIR}/fast.log"

    # 检查文件是否存在
    if [ ! -f "${LOG_DIR}/fast.log" ]; then
        echo "fast.log文件不存在"
    else
        echo "fast.log文件存在但为空"
    fi
fi

echo "================================="

# 可选: 恢复原始规则
read -p "是否恢复原始规则文件？[y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if [ -f "${RULES_DIR}/suricata.rules${BACKUP_SUFFIX}" ]; then
        mv "${RULES_DIR}/suricata.rules${BACKUP_SUFFIX}" "${RULES_DIR}/suricata.rules"
        echo "已恢复原始规则文件"
    else
        echo "备份文件不存在"
    fi
else
    echo "新规则已保留，原始规则备份在: ${RULES_DIR}/suricata.rules${BACKUP_SUFFIX}"
fi