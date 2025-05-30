

# 📚 小帅的小说爬虫

一个基于 **Python + PyQt6** 开发的图形化小说爬取工具，支持小说名称与作者精准匹配搜索、章节按序爬取、实时日志查看、进度追踪与中途停止。界面精美，操作简洁，是小说阅读爱好者的得力助手。

![image](https://github.com/user-attachments/assets/ee3efde9-7dc5-49fc-ac7d-ff542f038d6d)


---

## ✨ 功能特点

* 🔍 **精准搜索**
  支持 **小说名称 + 作者名** 双重精确匹配，找不到时自动进行模糊匹配，提高成功率。

* 📖 **章节爬取**
  自动识别章节结构，按顺序抓取内容并保存为 `.txt` 格式文件。

* ⏱️ **实时进度追踪**
  UI 显示当前进度条、已完成章节数与总章节数，进度一目了然。

* 📝 **实时日志输出**
  所有操作与网络请求均有日志记录，方便调试与用户查看过程。

* 🛑 **中途可中断**
  支持“停止爬取”操作，终止后展示爬取统计信息及保存路径。

* 🎨 **精美现代 UI**
  自定义标题栏设计，具备最小化、最大化与关闭功能，图标美观统一。

---

## 📦 项目结构

```bash
novel-spider/
├── main.py              # 主程序入口，启动图形界面
├── ui_main.py           # PyQt6 设计器生成的 UI 脚本
├── spider/              # 爬虫模块
│   ├── __init__.py
│   ├── search.py        # 小说搜索逻辑
│   └── crawler.py       # 小说章节爬取逻辑
├── utils/               # 工具模块（日志、弹窗、文件保存等）
│   ├── logger.py
│   ├── dialog.py
│   └── file_utils.py
├── assets/              # 图标与资源文件夹（如 PNG、ICO、JPG）
│   ├── 关闭.png
│   ├── 最小化.png
│   └── ...
├── requirements.txt     # Python 项目依赖列表
└── README.md            # 项目说明文件
```

---

## 💖 为爱发电

如果你喜欢这个项目，或者它对你有帮助，欢迎通过以下方式支持开发者持续创作：

| 微信赞赏 | 支付宝赞赏 |
| -------- | ---------- |
| <img src="https://github.com/user-attachments/assets/56c55ac6-e43f-480a-b87c-49c3eb61021e" width="300" height="400"> | <img src="https://github.com/user-attachments/assets/87747148-76f9-4cd7-8864-f48501bec597" width="300" height="400"> |




你的每一份支持，都是我继续优化的动力！✨

---

## 📄 开源协议

本项目遵循 [MIT License](LICENSE)，可自由使用与二次开发，欢迎 🌟Star 与 Fork！

---

