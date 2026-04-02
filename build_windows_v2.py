#!/usr/bin/env python
# encoding: utf-8
# @author: rockmelodies
# @license: (C) Copyright 2013-2024, 360 Corporation Limited.
# @contact: rockysocket@gmail.com
# @file: build_windows.py
# @time: 2024/6/18 17:30
# @desc: Windows平台打包脚本（详细过程输出和错误诊断）

import os
import sys
import subprocess
import platform
import shutil
import time
import tempfile
import json
from pathlib import Path
from tqdm import tqdm
import re


class BuildLogger:
    """详细的构建日志记录器"""

    def __init__(self):
        self.log_file = os.path.join("dist", "build_log.txt")
        self.error_log = os.path.join("dist", "error_log.txt")
        os.makedirs("dist", exist_ok=True)

    def log(self, message, level="INFO"):
        """记录日志"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] {message}"

        print(log_entry)

        # 写入日志文件
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(log_entry + "\n")

        if level in ["ERROR", "WARNING"]:
            with open(self.error_log, "a", encoding="utf-8") as f:
                f.write(log_entry + "\n")

    def section(self, title):
        """开始一个新的章节"""
        self.log("=" * 60)
        self.log(f"📋 {title}")
        self.log("=" * 60)

    def step(self, message):
        """记录步骤信息"""
        self.log(f"➡️  {message}")

    def success(self, message):
        """记录成功信息"""
        self.log(f"✅ {message}", "SUCCESS")

    def warning(self, message):
        """记录警告信息"""
        self.log(f"⚠️  {message}", "WARNING")

    def error(self, message):
        """记录错误信息"""
        self.log(f"❌ {message}", "ERROR")

    def debug(self, message):
        """记录调试信息"""
        self.log(f"🐛 {message}", "DEBUG")


def get_nuitka_version():
    """获取Nuitka版本信息"""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "nuitka", "--version"],
            capture_output=True, text=True, encoding='utf-8'
        )
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            return f"获取失败: {result.stderr}"
    except Exception as e:
        return f"异常: {str(e)}"


def find_upx(logger):
    """查找UPX可执行文件"""
    logger.step("查找UPX压缩工具")

    upx_paths = [
        "upx",
        "D:\\Program Files\\upx-5.0.2-win64\\upx.exe",
        os.path.join(os.getcwd(), "upx", "upx.exe"),
        os.path.join(os.getcwd(), "upx.exe"),
    ]

    for path in upx_paths:
        try:
            result = subprocess.run(
                [path, "--version"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0 and "UPX" in result.stdout:
                logger.success(f"找到UPX: {path}")
                logger.debug(f"UPX版本: {result.stdout.split()[1]}")
                return path
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            logger.debug(f"UPX路径 {path} 不可用: {str(e)}")
            continue

    logger.warning("未找到UPX，将不使用压缩")
    return None


def init_environment(logger):
    """初始化构建环境"""
    logger.section("初始化构建环境")

    env_info = {
        "Python版本": platform.python_version(),
        "工作目录": os.getcwd(),
        "Python路径": sys.executable,
        "操作系统": f"{platform.system()} {platform.release()}",
        "处理器": platform.processor(),
        "Nuitka版本": get_nuitka_version()
    }

    for key, value in env_info.items():
        logger.log(f"{key}: {value}")

    # 检查磁盘空间
    try:
        total, used, free = shutil.disk_usage(os.getcwd())
        logger.log(f"磁盘空间: 总共{total // (1024 ** 3)}GB, 可用{free // (1024 ** 3)}GB")
    except:
        logger.warning("无法获取磁盘空间信息")


def validate_paths(logger):
    """验证必要路径是否存在"""
    logger.section("验证文件路径")

    required_paths = {
        "主脚本": "src/main.py",
        "图标文件": "assets/icon.ico",
        "输出目录": "dist"
    }

    all_exists = True
    for name, path in required_paths.items():
        if os.path.exists(path):
            if os.path.isfile(path):
                size = os.path.getsize(path)
                logger.success(f"{name}: {path} ({size} bytes)")
            else:
                logger.success(f"{name}: {path} (目录)")
        else:
            logger.error(f"{name}不存在: {path}")
            all_exists = False

    if not all_exists:
        logger.error("缺少必要文件，构建终止")
        return False

    return True


def check_dependencies(logger):
    """检查必要的依赖是否安装"""
    logger.section("检查依赖包")

    dependencies = [
        ('PyQt6', 'PyQt6'),
        ('scapy', 'scapy'),
        ('nuitka', 'nuitka'),
        ('tqdm', 'tqdm')
    ]

    missing_deps = []
    for pip_name, import_name in dependencies:
        try:
            __import__(import_name)
            # 获取版本信息
            try:
                version = getattr(__import__(import_name), '__version__', '未知')
                logger.success(f"{pip_name}: 已安装 (v{version})")
            except:
                logger.success(f"{pip_name}: 已安装")
        except ImportError:
            missing_deps.append(pip_name)
            logger.error(f"{pip_name}: 未安装")

    if missing_deps:
        logger.error(f"缺少依赖包: {', '.join(missing_deps)}")
        logger.error("请运行: pip install " + " ".join(missing_deps))
        return False

    return True


def run_command_with_logging(cmd, logger, timeout=600):
    """运行命令并详细记录输出"""
    logger.debug(f"执行命令: {' '.join(cmd)}")

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        encoding='utf-8',
        errors='ignore',
        bufsize=1
    )

    output_lines = []
    try:
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                clean_line = line.strip()
                output_lines.append(clean_line)
                logger.debug(clean_line)

        return_code = process.wait(timeout=timeout)
        return return_code, output_lines

    except subprocess.TimeoutExpired:
        process.kill()
        logger.error("命令执行超时")
        return -1, output_lines


def build_with_nuitka(logger):
    """使用Nuitka打包（带详细日志记录）"""
    logger.section("开始Nuitka打包")

    upx_path = find_upx(logger)

    config = {
        "main_script": "src/main.py",
        "output_name": "HTTP流量包生成器",
        "icon_path": "assets/icon.ico",
        "dist_dir": "dist",
        "hidden_imports": [
            'scapy.all', 'scapy.layers.inet', 'scapy.layers.l2',
            'scapy.packet', 'PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.QtWidgets',
            'scapy.arch', 'scapy.arch.windows', 'scapy.data', 'scapy.plist',
            'scapy.error', 'scapy.utils', 'scapy.compat', 'scapy.sendrecv',
            'scapy.supersocket',
        ]
    }

    # 构建Nuitka命令
    nuitka_cmd = [
        sys.executable, "-m", "nuitka",
        "--standalone",
        "--onefile",
        "--enable-plugin=pyqt6",
        f"--output-dir={config['dist_dir']}",
        f"--output-filename={config['output_name']}",
        "--remove-output",
        "--assume-yes-for-downloads",
        "--show-progress",
        "--show-memory",
        f"--windows-icon-from-ico={config['icon_path']}",
        "--windows-uac-admin",
        "--windows-company-name=三六零数字安全科技集团有限公司",
        f"--windows-product-name={config['output_name']}",
        "--windows-file-version=1.0.0.0",
        "--windows-product-version=1.0.0.0",
        "--noinclude-pytest-mode=nofollow",
        "--noinclude-setuptools-mode=nofollow",
    ]

    if platform.system() == "Windows":
        nuitka_cmd.append("--windows-disable-console")

    if upx_path:
        nuitka_cmd.extend([f"--upx-binary={upx_path}", "--upx-enable"])
        logger.success("启用UPX压缩")

    for imp in config["hidden_imports"]:
        nuitka_cmd.append(f"--include-module={imp}")

    nuitka_cmd.append(config["main_script"])

    logger.step("开始执行Nuitka编译")
    start_time = time.time()

    try:
        return_code, output_lines = run_command_with_logging(nuitka_cmd, logger, timeout=1200)

        elapsed_time = time.time() - start_time
        logger.debug(f"编译耗时: {elapsed_time:.1f}秒")

        if return_code != 0:
            logger.error(f"Nuitka编译失败 (返回码: {return_code})")

            # 分析错误原因
            analyze_nuitka_errors(output_lines, logger)
            return False

        # 检查输出文件
        output_file = os.path.join(config['dist_dir'], config['output_name'] + '.exe')
        if os.path.exists(output_file):
            file_size = os.path.getsize(output_file) / (1024 * 1024)
            logger.success(f"打包成功! 文件: {output_file}")
            logger.success(f"文件大小: {file_size:.1f} MB")

            if upx_path:
                logger.success("已使用UPX压缩")

            return True
        else:
            logger.error("编译成功但输出文件未找到")
            return False

    except Exception as e:
        logger.error(f"编译过程异常: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def analyze_nuitka_errors(output_lines, logger):
    """分析Nuitka错误信息"""
    logger.section("错误分析")

    error_patterns = {
        "编译错误": r"error:|Error:",
        "导入错误": r"ImportError|ModuleNotFoundError|No module named",
        "语法错误": r"SyntaxError",
        "文件不存在": r"FileNotFoundError|No such file or directory",
        "权限错误": r"PermissionError",
        "内存错误": r"MemoryError|内存不足",
        "磁盘空间": r"disk space|磁盘空间",
        "UPX错误": r"upx|UPX",
        "MSVC错误": r"MSVC|Visual Studio|cl\.exe",
    }

    found_errors = set()
    last_10_lines = output_lines[-20:]  # 最后20行通常包含关键错误信息

    for line in last_10_lines:
        for error_type, pattern in error_patterns.items():
            if re.search(pattern, line, re.IGNORECASE):
                found_errors.add(error_type)
                logger.error(f"检测到{error_type}: {line}")

    # 提供解决方案建议
    if "编译错误" in found_errors:
        logger.error("💡 建议: 检查Python语法和依赖版本")

    if "导入错误" in found_errors:
        logger.error("💡 建议: 检查缺少的模块，可能需要添加 --include-module")

    if "MSVC错误" in found_errors:
        logger.error("💡 建议: 安装Visual Studio Build Tools或MSVC编译器")

    if "内存错误" in found_errors:
        logger.error("💡 建议: 关闭其他程序释放内存，或使用 --low-memory")

    if "磁盘空间" in found_errors:
        logger.error("💡 建议: 清理磁盘空间")

    if "UPX错误" in found_errors:
        logger.error("💡 建议: 检查UPX安装或使用 --no-upx 禁用压缩")

    if not found_errors:
        logger.warning("未识别到特定错误模式，请查看详细日志")
        for line in last_10_lines:
            logger.debug(line)


def create_simple_batch_installer(logger):
    """创建简单的批处理安装脚本"""
    logger.section("创建安装脚本")

    try:
        install_script = '''@echo off\nchcp 65001 >nul\necho 安装脚本内容...'''

        with open('dist/安装程序.bat', 'w', encoding='utf-8') as f:
            f.write(install_script)

        with open('dist/卸载程序.bat', 'w', encoding='utf-8') as f:
            f.write('@echo off\nchcp 65001 >nul\necho 卸载脚本内容...')

        logger.success("安装脚本创建完成")
        return True

    except Exception as e:
        logger.error(f"创建安装脚本失败: {str(e)}")
        return False


def generate_build_report(logger, success):
    """生成构建报告"""
    logger.section("构建报告")

    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "status": "成功" if success else "失败",
        "python_version": platform.python_version(),
        "nuitka_version": get_nuitka_version(),
        "output_file": os.path.join("dist", "HTTP流量包生成器.exe") if success else "无",
        "file_size": f"{os.path.getsize(os.path.join('dist', 'HTTP流量包生成器.exe')) / (1024 * 1024):.1f}MB" if success else "无"
    }

    report_file = os.path.join("dist", "build_report.json")
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    logger.success(f"构建报告已保存: {report_file}")


def main():
    """主函数"""
    logger = BuildLogger()

    try:
        logger.section("开始构建过程")

        # 环境初始化
        if not all([
            init_environment(logger),
            validate_paths(logger),
            check_dependencies(logger)
        ]):
            logger.error("环境检查失败，构建终止")
            return False

        # 执行打包
        success = build_with_nuitka(logger)

        if success:
            create_simple_batch_installer(logger)
            generate_build_report(logger, True)
            logger.section("🎉 构建成功完成!")
        else:
            generate_build_report(logger, False)
            logger.section("❌ 构建失败")

            # 提供调试建议
            logger.error("调试建议:")
            logger.error("1. 查看详细日志: dist/build_log.txt")
            logger.error("2. 检查错误信息: dist/error_log.txt")
            logger.error("3. 尝试简化命令: python -m nuitka --help")
            logger.error("4. 确保所有依赖已正确安装")

        return success

    except KeyboardInterrupt:
        logger.error("用户中断操作")
        return False
    except Exception as e:
        logger.error(f"发生未预期错误: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False
    finally:
        logger.log("构建过程结束")


if __name__ == '__main__':
    success = main()
    if not success and platform.system() == "Windows":
        input("\n按Enter键退出...")
    sys.exit(0 if success else 1)