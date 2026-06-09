"""SmartRPA 主入口 —— 在 VSCode 里直接 F5 运行"""
import sys, os

# 确保能找到 smartrpa 包
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gui import main

if __name__ == "__main__":
    main()

