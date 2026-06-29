"""AutoRewarder 启动脚本 — SmartRPA 集成

用法：
    python run_farmer.py --run     → SmartRPA exec 模式
    没有账号 → 自动打开 GUI 设置 → 关闭后跑 CLI
    有账号   → 直接跑 CLI
"""

import os
import sys
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CLI_PY = os.path.join(SCRIPT_DIR, "AutoRewarder_CLI.py")
GUI_PY = os.path.join(SCRIPT_DIR, "AutoRewarder.py")
REQ_PATH = os.path.join(SCRIPT_DIR, "requirements.txt")

# AutoRewarder 账号存储位置
ACCOUNTS_FILE = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
    "AutoRewarder", "accounts.json"
)


def get_python():
    """找到可用的 Python 解释器"""
    if getattr(sys, 'frozen', False):
        import shutil
        for name in ['python', 'python3', 'py']:
            found = shutil.which(name)
            if found: return found
        for base in [r'C:\Python313', r'C:\Program Files\Python313',
                      r'C:\Users\Administrator\AppData\Local\Programs\Python\Python313']:
            exe = os.path.join(base, 'python.exe')
            if os.path.exists(exe): return exe
        return None
    return sys.executable


def install_deps():
    """安装 AutoRewarder 依赖"""
    if not os.path.exists(REQ_PATH): return True
    python = get_python()
    if not python: return True
    try:
        subprocess.run(
            [python, "-m", "pip", "install", "-q", "-r", REQ_PATH,
             "-i", "https://pypi.tuna.tsinghua.edu.cn/simple"],
            check=True, timeout=300, cwd=SCRIPT_DIR
        )
        return True
    except Exception as e:
        print(f"pip install 失败: {e}")
        return False


def has_accounts():
    """检查是否已设置账号"""
    if not os.path.exists(ACCOUNTS_FILE): return False
    try:
        import json
        with open(ACCOUNTS_FILE, "r") as f:
            data = json.load(f)
        return isinstance(data, list) and len(data) > 0
    except Exception:
        return False


def launch_setup():
    """打开 AutoRewarder GUI 设置账号，等用户关窗口后返回"""
    print("未检测到账号，正在打开设置窗口...")
    python = get_python()
    if not python: return False
    subprocess.run([python, GUI_PY], cwd=SCRIPT_DIR, check=False)
    return has_accounts()


def run_cli():
    """无头模式运行 AutoRewarder"""
    if not os.path.exists(CLI_PY):
        print("AutoRewarder_CLI.py 不存在")
        return False
    python = get_python()
    if not python: return False
    subprocess.run([python, CLI_PY], cwd=SCRIPT_DIR, check=False)
    return True


if __name__ == "__main__":
    install_deps()

    if "--setup" in sys.argv:
        # 强制打开账号设置
        print("打开账号管理窗口...")
        launch_setup()
        sys.exit(0)

    if not has_accounts():
        print("=" * 40)
        print("  首次使用：请在弹窗中添加 Microsoft 账号")
        print("  添加完后关闭窗口即可自动开始")
        print("=" * 40)
        if not launch_setup():
            print("未检测到账号，请手动运行:")
            print(f"  python {GUI_PY}")
            sys.exit(1)

    print("运行 Bing Rewards 积分任务...")
    run_cli()
