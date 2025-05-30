import importlib

packages = [
    'time',         # 标准库，一定有
    'difflib',      # 标准库，一定有
    're',           # 标准库，一定有
    'requests',
    'bs4',          # BeautifulSoup 在包名是 bs4
    'PyQt6',
    'PyQt6.QtWidgets',
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'sys',          # 标准库，一定有
]

for pkg in packages:
    try:
        importlib.import_module(pkg)
        print(f"{pkg} 已安装")
    except ModuleNotFoundError:
        print(f"{pkg} 未安装")
