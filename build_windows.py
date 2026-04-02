# !/usr/bin/env python
# encoding: utf-8
# @author: rockmelodies
# @license: (C) Copyright 2013-2024, 360 Corporation Limited.
# @contact: rockysocket@gmail.com
# @file: build_windows.py
# @time: 2024/6/18 17:30
# @desc: Windows平台打包脚本（支持Nuitka进度显示）

import os
import sys
import subprocess
import platform
import shutil
from pathlib import Path
from tqdm import tqdm
import re


def init_environment():
    """初始化构建环境"""
    print("=" * 50)
    print(f"📦 初始化构建环境 (Python {platform.python_version()})")
    print(f"工作目录: {os.getcwd()}")
    print(f"Python路径: {sys.executable}")
    print("=" * 50 + "\n")


def validate_paths():
    """验证必要路径是否存在"""
    required_paths = {
        "主脚本": "src/main.py",
        "图标文件": "assets/icon.ico",
        "输出目录": "dist"
    }

    missing = []
    for name, path in required_paths.items():
        if not os.path.exists(path):
            missing.append(f"{name}:  {path}")

    if missing:
        print("❌ 缺失必要文件/目录:")
        print("\n".join(missing))
        sys.exit(1)


def build_with_nuitka():
    """使用Nuitka打包（带实时进度显示）"""
    print("🚀 开始Nuitka打包流程")

    # 基础配置
    config = {
        "main_script": "src/main.py",
        "output_name": "HTTP流量包生成器",
        "icon_path": "assets/icon.ico",
        "dist_dir": "dist",
        "hidden_imports": [
            'scapy.all',
            'scapy.layers.inet',
            'scapy.layers.l2',
            'scapy.packet',
            'PyQt6.QtCore',
            'PyQt6.QtGui',
            'PyQt6.QtWidgets',
        ],
        "include_data": {
            "assets/*": "assets/"
        }
    }

    # 构建Nuitka命令
    nuitka_cmd = [
        sys.executable, "-m", "nuitka",
        "--standalone",
        "--onefile",
        "--windows-disable-console" if platform.system() == "Windows" else "",
        "--enable-plugin=pyqt6",
        "--output-dir=" + config["dist_dir"],
        "--output-filename=" + config["output_name"],
        "--remove-output",
        "--assume-yes-for-downloads",
        "--show-progress",  # 关键：启用Nuitka原生进度输出
        "--show-memory",
        "--windows-icon-from-ico=" + config["icon_path"],
        "--windows-uac-admin",
        "--windows-company-name=三六零数字安全科技集团有限公司",
        "--windows-product-name=" + config["output_name"],
        "--windows-file-version=1.0.0",
        "--plugin-enable=implicit-imports",
        "--noinclude-pytest-mode=nofollow",
        "--noinclude-setuptools-mode=nofollow",
        "--windows-product-version=1.0.0",
    ]

    # 添加隐藏导入
    for imp in config["hidden_imports"]:
        nuitka_cmd.append(f"--include-module={imp}")

        # 添加数据文件
    for src, dest in config["include_data"].items():
        nuitka_cmd.append(f"--include-data-files={src}={dest}")

        # 添加主脚本（最终参数）
    nuitka_cmd.append(config["main_script"])

    # 过滤空参数
    nuitka_cmd = [arg for arg in nuitka_cmd if arg]

    try:
        print("\n🔧 执行的Nuitka命令:")
        print(" ".join(nuitka_cmd[:5]) + " [...] " + " ".join(nuitka_cmd[-2:]) + "\n")

        # 启动进度条
        with tqdm(
                total=100,
                desc="🛠 编译进度",
                bar_format="{l_bar}{bar}| {n:.0f}%/{total}%",
                colour="GREEN",
                dynamic_ncols=True
        ) as pbar:

            # 启动子进程
            process = subprocess.Popen(
                nuitka_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                encoding='utf-8',
                bufsize=1
            )

            # 进度匹配正则
            progress_re = re.compile(r"(\d+)%")
            last_progress = 0

            # 实时处理输出
            for line in iter(process.stdout.readline, ''):
                # 更新进度
                if match := progress_re.search(line):
                    new_progress = int(match.group(1))
                    pbar.update(new_progress - last_progress)
                    last_progress = new_progress

                    # 显示重要信息（过滤掉无关输出）
                if any(keyword in line.lower() for keyword in ["error", "warning", "note"]):
                    print(line.strip())

                    # 等待完成
            process.wait()
            if process.returncode != 0:
                raise subprocess.CalledProcessError(process.returncode, nuitka_cmd)

        print("\n" + "✅ 打包成功!".center(50, "="))
        print(f"输出文件: {os.path.abspath(os.path.join(config['dist_dir'], config['output_name'] + '.exe'))}")
        return True

    except subprocess.CalledProcessError as e:
        print("\n❌ Nuitka打包失败（返回码: {}）".format(e.returncode))
        print("请检查:")
        print("1. 是否安装了所有依赖（pip install -r requirements.txt ）")
        print("2. 是否有足够的磁盘空间")
        print("3. 是否在虚拟环境中运行")
        return False

    except Exception as e:
        print("\n❌ 发生未预期的错误:")
        print(str(e))
        return False


def create_installer():
    """创建NSIS安装包（仅Windows）"""
    if platform.system() != "Windows":
        return

    print("\n📦 正在创建安装包...")
    nsis_script = '''
    Unicode true
    Name "HTTP流量包生成器"
    OutFile "dist/HTTP流量包生成器_Setup.exe" 
    InstallDir "$PROGRAMFILES\\HTTP流量包生成器"
    RequestExecutionLevel admin 

    !include "MUI2.nsh" 

    !define MUI_ICON "assets/icon.ico" 
    !define MUI_WELCOMEFINISHPAGE_BITMAP "assets/splash.bmp" 

    !insertmacro MUI_PAGE_WELCOME 
    !insertmacro MUI_PAGE_DIRECTORY 
    !insertmacro MUI_PAGE_INSTFILES
    !insertmacro MUI_PAGE_FINISH

    !insertmacro MUI_LANGUAGE "SimpChinese"

    Section "主程序"
        SetOutPath "$INSTDIR"
        File "dist\\HTTP流量包生成器.exe"

        CreateDirectory "$SMPROGRAMS\\HTTP流量包生成器"
        CreateShortcut "$SMPROGRAMS\\HTTP流量包生成器\\HTTP流量包生成器.lnk" "$INSTDIR\\HTTP流量包生成器.exe"
        CreateShortcut "$DESKTOP\\HTTP流量包生成器.lnk" "$INSTDIR\\HTTP流量包生成器.exe"

        WriteUninstaller "$INSTDIR\\Uninstall.exe" 
        WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\HTTP流量包生成器" \\
            "DisplayName" "HTTP流量包生成器"
    SectionEnd

    Section "Uninstall"
        Delete "$INSTDIR\\HTTP流量包生成器.exe"
        Delete "$INSTDIR\\Uninstall.exe" 
        RMDir "$INSTDIR"

        Delete "$SMPROGRAMS\\HTTP流量包生成器\\HTTP流量包生成器.lnk"
        RMDir "$SMPROGRAMS\\HTTP流量包生成器"
        Delete "$DESKTOP\\HTTP流量包生成器.lnk"

        DeleteRegKey HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\HTTP流量包生成器"
    SectionEnd 
    '''

    # 写入NSIS脚本
    with open('setup.nsi', 'w', encoding='utf-8') as f:
        f.write(nsis_script)

        # 执行makensis
    try:
        subprocess.run(['makensis', 'setup.nsi'], check=True)
        print("✅ 安装包创建成功: dist/HTTP流量包生成器_Setup.exe")
    except FileNotFoundError:
        print("⚠️  未找到NSIS，跳过安装包创建（请安装NSIS并添加makensis到PATH）")
    except subprocess.CalledProcessError as e:
        print(f"❌ NSIS编译失败: {e}")


def main():
    # 初始化环境
    init_environment()
    validate_paths()

    # 执行打包
    if build_with_nuitka():
        create_installer()

    # 清理临时文件
    if os.path.exists("setup.nsi"):
        os.remove("setup.nsi")

    input("\n按Enter键退出...")


if __name__ == '__main__':
    main()