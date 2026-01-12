"""
跨平台打包脚本
使用 PyInstaller 将桌面启动入口 desktop_launcher.py 打成独立可执行文件。
"""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
LAUNCHER = ROOT / "desktop_launcher.py"
DIST_DIR = ROOT / "dist"
DEFAULT_NAME = "XianyuMonitor"


def ensure_frontend_built() -> None:
    """保证前端产物 dist 存在"""
    dist_path = ROOT / "dist"
    web_dist = ROOT / "web-ui" / "dist"

    if dist_path.exists():
        return

    if not web_dist.exists():
        raise RuntimeError("未找到 dist，请先在 web-ui 目录运行 npm run build")

    shutil.copytree(web_dist, dist_path)


def build(args: argparse.Namespace) -> None:
    """调用 PyInstaller 进行打包"""
    ensure_frontend_built()

    name = args.name or DEFAULT_NAME
    pyinstaller_args = [
        "--name",
        name,
        "--onefile",
        "--noconfirm",
        "--clean",
        "--add-data",
        f"{ROOT / 'dist'}{os.pathsep}dist",
        "--add-data",
        f"{ROOT / 'static'}{os.pathsep}static",
        "--add-data",
        f"{ROOT / 'prompts'}{os.pathsep}prompts",
        "--add-data",
        f"{ROOT / 'config.json'}{os.pathsep}.",
    ]

    # .env 可选
    env_file = ROOT / ".env"
    if env_file.exists():
        pyinstaller_args.extend(["--add-data", f"{env_file}{os.pathsep}."])

    # Playwright 资源自动收集
    pyinstaller_args.extend(["--collect-all", "playwright"])

    # 指定入口
    pyinstaller_args.append(str(LAUNCHER))

    print("运行 PyInstaller 参数:", " ".join(pyinstaller_args))
    subprocess.check_call([sys.executable, "-m", "PyInstaller", *pyinstaller_args])

    print(f"完成，产物位于 {ROOT / 'dist'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="PyInstaller 桌面打包脚本")
    parser.add_argument("--name", help="生成的可执行文件名，默认 XianyuMonitor")
    args = parser.parse_args()
    build(args)


if __name__ == "__main__":
    main()
