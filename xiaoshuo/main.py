import time
import difflib
import re
import requests
from bs4 import BeautifulSoup
from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QLineEdit, QPushButton, QTextEdit, QVBoxLayout, QHBoxLayout,QMessageBox, QProgressBar, QFrame, QVBoxLayout,QFileDialog
from PyQt6.QtCore import Qt, QThread, pyqtSignal,QSize
from PyQt6.QtGui import QFont,QIcon
import sys

# def resource_path(relative_path):
#     """获取资源文件的绝对路径（兼容PyInstaller打包）"""
#     try:
#         # PyInstaller打包后，资源会放在临时目录_sys._MEIPASS中
#         base_path = sys._MEIPASS
#     except Exception:
#         base_path = os.path.abspath(".")
#     return os.path.join(base_path, relative_path)

# ---------- 爬虫函数（你提供的代码，稍作改造以支持中断和日志回调） ----------

base_url = "https://www.00shu.la"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
}

def normalize(text):
    return text.strip().lower()

def int_to_chinese(num):
    units = ['', '十', '百', '千']
    nums = ['零', '一', '二', '三', '四', '五', '六', '七', '八', '九']

    if num == 0:
        return nums[0]

    result = ''
    str_num = str(num)
    length = len(str_num)

    for i, digit_char in enumerate(str_num):
        digit = int(digit_char)
        pos = length - i - 1

        if digit != 0:
            if not (digit == 1 and pos == 1 and result == ''):
                result += nums[digit]
            result += units[pos]
        else:
            if i < length - 1 and str_num[i + 1] != '0':
                result += nums[0]

    if result.startswith('一十'):
        result = result[1:]

    return result

def chinese_num_to_int(cn):
    cn_num = {
        '零':0, '一':1, '二':2, '三':3, '四':4, '五':5, '六':6,
        '七':7, '八':8, '九':9, '十':10
    }
    if not cn:
        return None
    if cn.isdigit():
        return int(cn)
    if len(cn) == 1:
        return cn_num.get(cn, None)
    if len(cn) == 2:
        if cn[0] == '十':
            return 10 + cn_num.get(cn[1], 0)
        elif cn[1] == '十':
            return cn_num.get(cn[0], 0) * 10
    if len(cn) == 3 and cn[1] == '十':
        return cn_num.get(cn[0], 0) * 10 + cn_num.get(cn[2], 0)
    return None

def extract_chapter_number(title):
    m = re.match(r"第([零一二三四五六七八九十百千万\d]+)章", title)
    if m:
        num_str = m.group(1)
        if num_str.isdigit():
            return int(num_str)
        else:
            return chinese_num_to_int(num_str)
    m2 = re.match(r"([零一二三四五六七八九十百千万\d]+)章", title)
    if m2:
        num_str = m2.group(1)
        if num_str.isdigit():
            return int(num_str)
        else:
            return chinese_num_to_int(num_str)
    return None

def process_title(raw_title, chapter_num):
    extracted_num = extract_chapter_number(raw_title)
    chapter_num_cn = int_to_chinese(chapter_num)

    if re.match(r"^第[零一二三四五六七八九十百千万\d]+章", raw_title) and extracted_num is not None:
        if extracted_num != chapter_num:
            new_title = re.sub(
                r"第[零一二三四五六七八九十百千万\d]+章",
                f"第{chapter_num_cn}章",
                raw_title
            )
            return new_title
        else:
            new_title = re.sub(
                r"第(\d+)章",
                f"第{chapter_num_cn}章",
                raw_title
            )
            return new_title

    if extracted_num is not None:
        new_title = re.sub(
            r"^[零一二三四五六七八九十百千万\d]+章",
            f"第{chapter_num_cn}章",
            raw_title
        )
        return new_title

    return f"第{chapter_num_cn}章 {raw_title}"

def get_best_match_first_chapter(book_name, author_name, log_func):
    try:
        search_url = f"{base_url}/modules/article/search.php?q={book_name}"
        res = requests.get(search_url, headers=headers, timeout=10)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')

        rows = soup.select("table.grid tr#nr")
        candidates = []

        for row in rows:
            title_a = row.select_one("td.odd a")
            title = title_a.text.strip() if title_a else ""
            book_url = title_a["href"] if title_a else ""

            td_tags = row.find_all("td", class_="odd")
            author = td_tags[1].get_text(strip=True) if len(td_tags) > 1 else ""

            if title and book_url:
                candidates.append({
                    "title": title,
                    "author": author,
                    "url": book_url
                })

        if not candidates:
            log_func("❌ 搜索结果为空")
            return None

        if author_name == "no":
            for book in candidates:
                if normalize(book["title"]) == normalize(book_name):
                    log_func(f"✅ 找到完全匹配（无作者限制）：{book['title']}（作者：{book['author']}）")
                    return get_first_chapter_link(book["url"], log_func)
        else:
            for book in candidates:
                if normalize(book["title"]) == normalize(book_name) and normalize(book["author"]) == normalize(author_name):
                    log_func(f"✅ 找到完全匹配（有作者限制）：{book['title']}（作者：{book['author']}）")
                    return get_first_chapter_link(book["url"], log_func)

        scored_books = []
        for book in candidates:
            title_score = difflib.SequenceMatcher(None, book_name, book["title"]).ratio()
            author_score = difflib.SequenceMatcher(None, author_name, book["author"]).ratio() if author_name != "no" else 0.0
            total_score = title_score * 0.7 + author_score * 0.3
            scored_books.append((total_score, book))

        best_match = max(scored_books, key=lambda x: x[0])
        best_book = best_match[1]

        log_func(f"⚠️ 未找到完全匹配，选择最相近：{best_book['title']}（作者：{best_book['author']}），匹配评分：{best_match[0]:.2f}")
        return get_first_chapter_link(best_book["url"], log_func)

    except Exception as e:
        log_func(f"❌ 搜索失败：{e}")
        return None

def get_first_chapter_link(book_url, log_func):
    try:
        res = requests.get(book_url, headers=headers, timeout=10)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')
        first_chapter = soup.select_one("div#list dd a")
        if first_chapter:
            return base_url + first_chapter["href"]
        else:
            log_func("❌ 未找到章节目录")
            return None
    except Exception as e:
        log_func(f"❌ 获取章节失败：{e}")
        return None

def get_chapter(url, chapter_num, retries=3, timeout=10, log_func=None):
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=headers, timeout=timeout)
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, 'html.parser')

            title_tag = soup.select_one("div.bookname h1")
            raw_title = title_tag.get_text(strip=True) if title_tag else "无标题"

            title = process_title(raw_title, chapter_num)

            content_tag = soup.find("div", id="content")
            if content_tag:
                for tip in content_tag.select("div#content_tip"):
                    tip.extract()
                content = content_tag.get_text("\n", strip=True)
            else:
                content = "未获取到正文内容"

            next_tag = soup.find("a", string="下一章")
            next_url = base_url + next_tag["href"] if next_tag and next_tag.get("href") else None

            return raw_title, title, content, next_url

        except Exception as e:
            if log_func:
                log_func(f"⚠️ 第 {attempt+1} 次尝试失败：{e}")
            time.sleep(1)

    return None, None, None, None

def save_to_txt(output_file, title, content):
    with open(output_file, "a", encoding="utf-8") as f:
        f.write(title + "\n\n")
        f.write(content + "\n\n")

# -------------- 线程类保持不变 --------------
class CrawlerThread(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal(str)

    def __init__(self, book_name, author_name, output_file):
        super().__init__()
        self.book_name = book_name
        self.author_name = author_name
        self.output_file = output_file
        self._is_running = True

    def stop(self):
        self._is_running = False

    def run(self):
        with open(self.output_file, "w", encoding="utf-8") as f:
            f.write("")

        def log_func(msg):
            self.log_signal.emit(msg)

        log_func(f"开始搜索小说《{self.book_name}》 作者：{self.author_name}")

        first_chapter_url = get_best_match_first_chapter(self.book_name, self.author_name, log_func)
        if not first_chapter_url:
            self.finished_signal.emit("未找到小说章节起始链接，程序退出。")
            return

        log_func(f"开始爬取章节列表，起始URL：{first_chapter_url}")

        url = first_chapter_url
        chapter_num = 1

        while url and self._is_running:
            log_func(f"\n📖 正在爬取第 {chapter_num} 章：{url}")
            raw_title, title, content, next_url = get_chapter(url, chapter_num, log_func=log_func)

            if content:
                log_func(f"🔎 div.bookname h1 原始标题内容：{raw_title}")
                log_func(f"✅ 处理后的标题：{title}")
                save_to_txt(self.output_file, title, content)
                url = next_url
                chapter_num += 1
                self.progress_signal.emit(chapter_num)
                time.sleep(0.1)
            else:
                log_func("❌ 获取失败，已终止爬取。")
                break

        if self._is_running:
            log_func(f"\n✅ 爬取完成，小说保存至：{self.output_file}")
            self.finished_signal.emit("爬取完成")
        else:
            log_func(f"\n⏹️ 用户停止了爬取，已保存至：{self.output_file}")
            self.finished_signal.emit("用户停止了爬取")
#-----------------
class HoverIconButton(QPushButton):
    def __init__(self, normal_icon_path, hover_icon_path, size, parent=None):
        super().__init__(parent)
        self.normal_icon = QIcon(normal_icon_path)
        self.hover_icon = QIcon(hover_icon_path)
        self.setFixedSize(size)
        self.setIcon(self.normal_icon)
        self.setIconSize(size)
        self.setStyleSheet("background-color: none; border: none;")  # 你原先的样式

    def enterEvent(self, event):
        self.setIcon(self.hover_icon)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setIcon(self.normal_icon)
        super().leaveEvent(event)
# -------------- 美化UI的主窗口 --------------


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("小说爬取器 - 小帅")
        self.resize(800, 600)

        # 关键：去除系统边框和标题栏
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        self._drag_pos = None  # 用于存储拖动起点坐标

        # 设置整体字体
        self.setFont(QFont("微软雅黑", 10))

        # 背景色和圆角
        self.setStyleSheet("""
            QWidget#MainWidget {
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1,
                stop:0 #dae6f3, stop:1 #f9faff);
                border-radius: 10px;
            }
        """)

        main_widget = QFrame(self)
        main_widget.setObjectName("MainWidget")
        main_widget.setGeometry(10, 10, 780, 580)
        main_widget.setStyleSheet("""
            QFrame#MainWidget {
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1,
                stop:0 #dae6f3, stop:1 #f9faff);
                border-radius: 10px;
            }
        """)

        # 输入部分
        self.label_book = QLabel("小说名称:")
        self.label_author = QLabel("作者名称 (无作者填 no):")

        self.input_book = QLineEdit()
        self.input_author = QLineEdit()

        # 输入框样式
        line_edit_style = """
            QLineEdit {
                border: 2px solid #87a9d6;
                border-radius: 6px;
                padding: 6px 10px;
                background: #f0f5fb;
                selection-background-color: #a0c8ff;
            }
            QLineEdit:focus {
                border-color: #3a78d8;
                background: #e7f0ff;
            }
        """
        self.input_book.setStyleSheet(line_edit_style)
        self.input_author.setStyleSheet(line_edit_style)

        # 按钮
        self.btn_start = QPushButton("开始爬取")
        self.btn_stop = QPushButton("停止爬取")
        self.btn_stop.setEnabled(False)

        btn_style = """
            QPushButton {
                background-color: #3a78d8;
                color: white;
                border-radius: 8px;
                padding: 10px 25px;
                font-weight: bold;
                transition: background-color 0.3s;
            }
            QPushButton:hover {
                background-color: #2a5db8;
            }
            QPushButton:disabled {
                background-color: #9bb8e9;
            }
        """
        self.btn_start.setStyleSheet(btn_style)
        self.btn_stop.setStyleSheet(btn_style)

        # 日志显示区
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #ffffff;
                border: 2px solid #87a9d6;
                border-radius: 8px;
                padding: 10px;
                font-family: Consolas, Courier New, monospace;
                font-size: 12px;
                color: #333333;
            }
        """)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(0)  # 不确定进度时为忙碌状态
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #87a9d6;
                border-radius: 8px;
                text-align: center;
                background: #f0f5fb;
                color: #555555;
                font-weight: bold;
            }
            # （续写）设置进度条样式
QProgressBar::chunk {
    background-color: #3a78d8;
    width: 20px;
}
""")

        title_layout = QHBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)  # 去掉边距
        title_layout.setSpacing(30)  # 按钮间距

        title_label = QLabel("小帅的小说爬虫软件")
        title_label.setStyleSheet("color: #2a5db8; font-size: 18px; font-weight: bold;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        # btn_min = HoverIconButton(resource_path("最小化.png"), resource_path("最小化-蓝色.png"), QSize(25, 25))
        # btn_max = HoverIconButton(resource_path("最大化.png"), resource_path("最大化-蓝色.png"), QSize(19, 19))
        # btn_close = HoverIconButton(resource_path("关闭.png"), resource_path("关闭-蓝色.png"), QSize(20, 20))
        btn_min = HoverIconButton("./最小化.png", "./最小化-蓝色.png", QSize(25, 25))
        btn_max = HoverIconButton("./最大化.png", "./最大化-蓝色.png", QSize(25, 25))
        btn_close = HoverIconButton("./关闭.png", "./关闭-蓝色.png", QSize(25, 25))

        title_layout.addWidget(title_label)
        title_layout.addStretch()  # 推动后续按钮靠右
        title_layout.addWidget(btn_min)
        title_layout.addWidget(btn_max)
        title_layout.addWidget(btn_close)

        # 样式：无背景色，鼠标悬停变浅灰色
        btn_style = """
            QPushButton {
                background-color: none;
                border: none;
            }
            QPushButton:hover {
                background-color: ;
                border-radius: none;
            }
        """
        for btn in [btn_min, btn_max, btn_close]:
            btn.setStyleSheet(btn_style)

        # 绑定事件
        btn_min.clicked.connect(self.showMinimized)
        btn_max.clicked.connect(self.toggle_max_restore)
        btn_close.clicked.connect(self.close)

        self.is_maximized = False

        # 后面你的整体布局保持不变
        layout = QVBoxLayout(main_widget)
        layout.setSpacing(12)
        layout.addLayout(title_layout)
        layout.addWidget(self.label_book)
        layout.addWidget(self.input_book)
        layout.addWidget(self.label_author)
        layout.addWidget(self.input_author)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.btn_start)
        btn_layout.addWidget(self.btn_stop)
        layout.addLayout(btn_layout)

        layout.addWidget(self.progress_bar)
        layout.addWidget(self.log_text)

        # 初始化线程为 None
        self.crawler_thread = None

        # 绑定按钮事件
        self.btn_start.clicked.connect(self.start_crawling)
        self.btn_stop.clicked.connect(self.stop_crawling)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        event.accept()

    def toggle_max_restore(self):
        if self.is_maximized:
            self.showNormal()
        else:
            self.showMaximized()
        self.is_maximized = not self.is_maximized

    def start_crawling(self):
        book_name = self.input_book.text().strip()
        author_name = self.input_author.text().strip()

        if not book_name:
            QMessageBox.warning(self, "输入错误", "请输入小说名称")
            return

        # 默认保存路径
        self.output_path = f"{book_name}.txt"

        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)

        self.thread = CrawlerThread(book_name, author_name, self.output_path)
        self.thread.log_signal.connect(self.append_log)
        self.thread.progress_signal.connect(self.update_progress)
        self.thread.finished_signal.connect(self.crawling_finished)
        self.thread.start()

    def stop_crawling(self):
        if hasattr(self, 'thread') and self.thread and self.thread.isRunning():
            file_path, _ = QFileDialog.getSaveFileName(
                self, "保存小说文件", self.output_path, "Text Files (*.txt)"
            )
            if file_path:
                # 重命名当前保存的 txt 文件
                try:
                    import shutil
                    shutil.move(self.output_path, file_path)
                    self.append_log(f"📁 已将小说文件保存至：{file_path}")
                except Exception as e:
                    self.append_log(f"❌ 保存失败：{e}")
            self.thread.stop()
            self.thread.wait()

    def update_progress(self, count):
        self.progress_bar.setMaximum(10000)  # 任意大值
        self.progress_bar.setValue(count)

    def crawling_finished(self, msg):
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        QMessageBox.information(self, "完成", msg)

    def append_log(self, text):
        self.log_text.append(text)

    def closeEvent(self, event):
        if hasattr(self, 'thread') and self.thread.isRunning():
            self.thread.stop()
            self.thread.wait()
        event.accept()


# 运行程序
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())