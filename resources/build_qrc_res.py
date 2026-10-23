"""
python -m PyQt5.pyrcc_main resources.qrc -o resources_rc.py
Note: modify PyQt5 to PyQt6 in the .py if using PyQt6
"""

import subprocess
import os
import sys


def build_qrc():
    qrc_file = "resources.qrc"
    output_file = "resources_rc.py"

    print("=" * 50)
    print(" ⚡ 開始自動化 QRC 資源編譯與 PyQt6 轉換 ⚡")
    print("=" * 50)

    # 1. 檢查原始 QRC 檔案是否存在
    if not os.path.exists(qrc_file):
        print(f"❌ 錯誤：找不到資源定義檔 '{qrc_file}'！")
        return

    # 2. 執行命令生成資源檔
    print(f"1. 正在編譯 {qrc_file} ...")
    cmd = [sys.executable, "-m", "PyQt5.pyrcc_main", qrc_file, "-o", output_file]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print("❌ 編譯失敗！錯誤訊息如下：")
        print(result.stderr)
        print("\n請確保環境中有安裝 PyQt5：pip install PyQt5")
        return

    # 3. 自動讀取產出的檔案，將 PyQt5 字串全部替換成 PyQt6
    print("2. 正在進行 PyQt6 關鍵字自動相容性轉換...")
    try:
        with open(output_file, "r", encoding="utf-8") as f:
            content = f.read()

        # 替換模組名稱
        modified_content = content.replace("PyQt5", "PyQt6")

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(modified_content)

        print(f"✨ 成功：已產出完美支援 PyQt6 的 '{output_file}'！")

    except Exception as e:
        print(f"❌ 轉換文字時發生錯誤: {e}")

    print("=" * 50)
    input()


if __name__ == "__main__":
    build_qrc()
