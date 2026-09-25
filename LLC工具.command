#!/bin/bash
# Power Design Toolkit - macOS one-click GUI launcher
# Place in the repo root; double-click to open the workspace GUI.

cd "$(dirname "$0")" || exit 1

# Keep Chinese/English messages readable in Terminal.app
export LANG="${LANG:-zh_CN.UTF-8}"
export LC_ALL="${LC_ALL:-zh_CN.UTF-8}"
export PYTHONIOENCODING=utf-8

# Prefer known project envs, then local .venv, then PATH python3
PY=""
for candidate in \
    "/Users/yangshuai/Applications/Python_Envs/power-tools-py312/bin/python" \
    "/Users/yangshuai/venvs/sci/bin/python" \
    "./.venv/bin/python"
do
    if [ -x "$candidate" ]; then
        PY="$candidate"
        break
    fi
done
if [ -z "$PY" ] && command -v python3 >/dev/null 2>&1; then
    PY="$(command -v python3)"
fi

if [ -z "$PY" ]; then
    echo "错误: 未找到 Python 3 (需要 >=3.10)。"
    read -r -p "按回车退出..."
    exit 1
fi

# First run: install package + GUI deps if missing
if ! "$PY" -c "import llc_design, pfc_design, PySide6" >/dev/null 2>&1; then
    echo "首次运行: 正在安装 power-design-toolkit (含 GUI 依赖) ..."
    if ! "$PY" -m pip install -e ".[gui]"; then
        echo "pip 安装失败, 尝试在本目录创建 .venv ..."
        if command -v python3 >/dev/null 2>&1; then
            python3 -m venv .venv
            PY="./.venv/bin/python"
            "$PY" -m pip install -e ".[gui]"
        fi
    fi
    if ! "$PY" -c "import llc_design, pfc_design, PySide6" >/dev/null 2>&1; then
        echo "安装失败, 请检查网络或 pip 配置。"
        read -r -p "按回车退出..."
        exit 1
    fi
fi

echo "正在启动电源设计工具图形界面..."
echo "Python: $PY"
"$PY" -m llc_design gui
status=$?
if [ "$status" -ne 0 ]; then
    echo "启动失败 (exit=$status)。"
    read -r -p "按回车退出..."
fi
exit "$status"
