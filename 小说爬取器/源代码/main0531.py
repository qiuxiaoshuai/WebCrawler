import time
import difflib
import re
import requests
from bs4 import BeautifulSoup
from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QLineEdit, QPushButton, QTextEdit, QVBoxLayout, QHBoxLayout,QMessageBox, QProgressBar, QFrame, QVBoxLayout,QFileDialog,QDialog
from PyQt6.QtCore import Qt, QThread, pyqtSignal,QSize
from PyQt6.QtGui import QFont,QIcon,QPixmap
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

base_url = "https://www.00shu.la"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
}
# 获取所有章节
def get_all_chapters(book_url, log_func):
    try:
        res = requests.get(book_url, headers=headers, timeout=10)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')
        chapter_tags = soup.select("div#list dd a")

        chapter_links = []
        for idx, tag in enumerate(chapter_tags, 1):
            href = tag["href"]
            chapter_url = base_url + href
            chapter_links.append((idx, chapter_url))

        log_func(f"📚 共获取到 {len(chapter_links)} 个章节链接。")
        return chapter_links

    except Exception as e:
        log_func(f"❌ 获取章节目录失败：{e}")
        return []


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

        if author_name == "":
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

def get_chapter(url, chapter_num, retries=3, timeout=10, log_func=None, stop_flag=None):
    for attempt in range(retries):
        if stop_flag and stop_flag():
            if log_func:
                log_func(f"⏹️ 停止爬取，跳过第{chapter_num}章")
            return None, None, None, None
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
    total_signal = pyqtSignal(int)  # 新增：发送总章节数

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

        stop_flag = lambda: not self._is_running
        log_func(f"开始搜索小说《{self.book_name}》 作者：{self.author_name}")

        first_chapter_url = get_best_match_first_chapter(self.book_name, self.author_name, log_func)
        if not first_chapter_url:
            self.total_signal.emit(0)  # 添加此行，通知界面总章节为0
            self.finished_signal.emit("未找到小说章节起始链接，程序退出。")
            return

        book_url = re.sub(r"/\d+\.html$", "/", first_chapter_url)
        all_chapters = get_all_chapters(book_url, log_func)

        if not all_chapters:
            self.finished_signal.emit("未能获取章节列表")
            return
        self.total_signal.emit(len(all_chapters))  # 发送总章节数
        results = {}
        max_threads = 8  # 可调节线程数量
        with ThreadPoolExecutor(max_workers=max_threads) as executor:
            future_to_chapter = {
                executor.submit(get_chapter, url, idx, 3, 10, log_func,stop_flag): (idx, url)
                for idx, url in all_chapters
            }

            for count, future in enumerate(as_completed(future_to_chapter), 1):
                if not self._is_running:
                    break

                idx, url = future_to_chapter[future]
                try:
                    raw_title, title, content, _ = future.result()
                    if content:
                        results[idx] = (title, content)
                        self.progress_signal.emit(count)
                        log_func(f"✅ 第 {idx} 章获取成功")
                    else:
                        log_func(f"⚠️ 第 {idx} 章内容为空")
                except Exception as e:
                    log_func(f"❌ 第 {idx} 章爬取失败：{e}")

        # 排序写入文件
        with open(self.output_file, "a", encoding="utf-8") as f:
            for idx in sorted(results):
                title, content = results[idx]
                f.write(f"{title}\n\n{content}\n\n")

        if self._is_running:
            log_func(f"\n✅ 多线程爬取完成，小说保存至：{self.output_file}")
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
    save_file_signal = pyqtSignal()  # 新增信号，用于触发文件保存对话框
    def __init__(self):
        super().__init__()
        self.setWindowTitle("小说爬取器")
        self.resize(800, 600)

        # 连接信号到槽
        self.save_file_signal.connect(self.show_save_dialog)
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
        self.label_author = QLabel("作者名称 (不知道作者请空着):")

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

        # 这里加进主布局，假设self.layout是已有的布局
        self.layout = QVBoxLayout(self)
        self.layout.addWidget(self.progress_bar)
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

        # 顶部标题布局
        title_layout = QHBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)  # 去掉边距
        title_layout.setSpacing(10)  # 左右元素之间的间距

        # 图标标签（放在文字左侧）
        icon_label = QLabel()
        icon_pixmap = QPixmap("./1234.jpg")
        icon_pixmap = icon_pixmap.scaled(QSize(40, 40), Qt.AspectRatioMode.KeepAspectRatio,
                                         Qt.TransformationMode.SmoothTransformation)
        icon_label.setPixmap(icon_pixmap)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        # 标题标签
        title_label = QLabel("小说爬取器 - 小帅")
        title_label.setStyleSheet("color: #2a5db8; font-size: 18px; font-weight: bold;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        # 左侧布局：图标 + 标题
        title_left_layout = QHBoxLayout()
        title_left_layout.setContentsMargins(0, 0, 0, 0)
        title_left_layout.setSpacing(5)
        title_left_layout.addWidget(icon_label)
        title_left_layout.addWidget(title_label)

        title_left_widget = QWidget()
        title_left_widget.setLayout(title_left_layout)

        # 右侧按钮
        btn_min = HoverIconButton("./最小化.png", "./最小化-蓝色.png", QSize(25, 25))
        btn_max = HoverIconButton("./最大化.png", "./最大化-蓝色.png", QSize(25, 25))
        btn_close = HoverIconButton("./关闭.png", "./关闭-蓝色.png", QSize(25, 25))

        # 添加到主标题栏
        title_layout.addWidget(title_left_widget)
        title_layout.addStretch()
        title_layout.addWidget(btn_min)
        title_layout.addWidget(btn_max)
        title_layout.addWidget(btn_close)

        # 设置按钮样式
        btn_style = """
            QPushButton {
                background-color: none;
                border: none;
            }
            QPushButton:hover {
                background-color: none;
                border-radius: none;
            }
        """
        for btn in [btn_min, btn_max, btn_close]:
            btn.setStyleSheet(btn_style)

        # 按钮功能绑定
        btn_min.clicked.connect(self.showMinimized)
        btn_max.clicked.connect(self.toggle_max_restore)
        btn_close.clicked.connect(self.close)
        self.is_maximized = False

        # 主界面布局
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

        # 初始化线程
        self.crawler_thread = None
        self.crawler_thread = CrawlerThread("", "", "")

        # 绑定按钮事件
        self.btn_start.clicked.connect(self.start_crawling)
        self.btn_stop.clicked.connect(self.stop_crawling)

    # def save_log_to_file(self, file_path):
    #     try:
    #         with open(file_path, 'w', encoding='utf-8') as f:
    #             f.write(self.log_text.toPlainText())
    #         QMessageBox.information(self, "保存成功", f"日志已保存至 {file_path}")
    #     except Exception as e:
    #         QMessageBox.warning(self, "保存失败", f"保存文件时出错: {e}")

    def show_save_dialog(self):
        # 非阻塞方式弹出保存对话框
        dialog = QFileDialog(self, "选择保存路径", "", "文本文件 (*.txt)")
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        dialog.setFileMode(QFileDialog.FileMode.AnyFile)
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)  # 可选，避免系统模态
        dialog.fileSelected.connect(self.save_log_to_file)  # 选择文件后回调
        dialog.open()  # 非阻塞打开对话框
    #完成ON后
    def on_finished(self, msg):
        self.log_text.append(msg)
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)

        # # 弹出保存文件对话框
        # file_path, _ = QFileDialog.getSaveFileName(self, "选择保存路径", "", "文本文件 (*.txt)")
        # if file_path:
        #     try:
        #         # 将已有内容写入选定文件
        #         with open(file_path, 'w', encoding='utf-8') as f:
        #             f.write(self.log_text.toPlainText())
        #         QMessageBox.information(self, "保存成功", f"日志已保存至 {file_path}")
        #     except Exception as e:
        #         QMessageBox.warning(self, "保存失败", f"保存文件时出错: {e}")
        self.save_file_signal.emit()
    #开始_绘制
    def start_crawling(self):
        # 选择保存文件路径
        file_path, _ = QFileDialog.getSaveFileName(self, "选择保存路径", "", "文本文件 (*.txt)")
        if not file_path:
            QMessageBox.warning(self, "警告", "必须选择保存路径！")
            return

        book_name = self.input_book.text().strip()
        author_name = self.input_author.text().strip()
        if not book_name:
            QMessageBox.warning(self, "警告", "请输入小说名称")
            return

        self.crawler_thread = CrawlerThread(book_name, author_name, file_path)
        self.crawler_thread.log_signal.connect(self.append_log)
        self.crawler_thread.progress_signal.connect(self.update_progress)
        self.crawler_thread.finished_signal.connect(self.on_finished)
        self.crawler_thread.start()

        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
    #停止绘制
    def stop_crawling(self):
        if hasattr(self, 'crawler_thread'):
            self.crawler_thread.stop()
    #鼠标按下事件
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
    #mouseMove事件
    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
    #释放事件
    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        event.accept()
    #修复
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

        self.crawler_thread.progress_signal.connect(self.update_progress)
        self.crawler_thread.total_signal.connect(self.set_progress_max)
        self.crawler_thread.log_signal.connect(self.append_log)
        self.crawler_thread.finished_signal.connect(self.crawl_finished)

    def set_progress_max(self, total):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(0)  # 进度条重置
    def update_progress(self, value):
        self.progress_bar.setValue(value)
        self.progress_bar.setMaximum(10000)  # 任意大值

    def append_log(self, text):
        self.log_text.append(text)

    def crawl_finished(self, msg):
        self.log_text.append(msg)
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)

        if msg == "爬取完成":  # 正常完成时弹窗
            file_path, _ = QFileDialog.getSaveFileName(self, "保存小说文件", self.output_path, "Text Files (*.txt)")
            if file_path:
                import shutil
                try:
                    shutil.move(self.output_path, file_path)
                    self.append_log(f"📁 已将小说文件保存至：{file_path}")
                except Exception as e:
                    self.append_log(f"❌ 保存失败：{e}")
        self.show_support_dialog()

    def stop_crawling(self):
        if hasattr(self, 'thread') and self.thread and self.thread.isRunning():
            # 先停止线程
            self.thread.stop()
            self.thread.wait()

            # 弹出保存文件对话框，默认路径可以是之前的 output_path
            file_path, _ = QFileDialog.getSaveFileName(
                self, "保存小说文件", self.output_path, "Text Files (*.txt)"
            )
            if file_path:
                try:
                    import shutil
                    shutil.move(self.output_path, file_path)
                    self.append_log(f"📁 已将小说文件保存至：{file_path}")
                except Exception as e:
                    self.append_log(f"❌ 保存失败：{e}")
            else:
                self.append_log("⚠️ 用户取消了保存操作。")
            # self.show_support_dialog()

    # def update_progress(self, count):
    #     self.progress_bar.setMaximum(10000)  # 任意大值
    #     self.progress_bar.setValue(count)

    #爬虫已完成
    def crawling_finished(self, msg):
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.show_support_dialog()
        QMessageBox.information(self, "完成", msg)

    # def append_log(self, text):
    #     self.log_text.append(text)

    def closeEvent(self, event):
        if hasattr(self, 'thread') and self.thread.isRunning():
            self.thread.stop()
            self.thread.wait()
        event.accept()

    def show_support_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("为爱发电")
        dialog.resize(600, 700)

        main_layout = QVBoxLayout()

        # 优化后的文字说明
        label_text = QLabel()
        label_text.setTextFormat(Qt.TextFormat.RichText)  # 支持 HTML 格式
        label_text.setText(
            """
            <div style="text-align: center; font-family: 微软雅黑; font-size: 16px; color: #444;">
                <p><b>感谢使用 <span style="color: #0078d4;">小帅的小说爬取器</span>！</b></p>
                <p>如果你觉得本项目对你有帮助，欢迎为爱发电支持开发者持续更新 ❤️</p>
                <p>项目已在Github开源：</p>
                <p><a href='https://github.com/qiuxiaoshuai/WebCrawler.git'>https://github.com/qiuxiaoshuai/WebCrawler.git</a></p>
            </div>
            """
        )
        label_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label_text.setWordWrap(True)
        main_layout.addWidget(label_text)

        # 横向布局用于放置两张付款码图片
        image_layout = QHBoxLayout()

        pay_pixmap1 = QPixmap("微信.jpg")
        pay_label1 = QLabel()
        pay_label1.setPixmap(pay_pixmap1.scaled(250, 300, Qt.AspectRatioMode.KeepAspectRatio,
                                                Qt.TransformationMode.SmoothTransformation))
        pay_label1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image_layout.addWidget(pay_label1)

        pay_pixmap2 = QPixmap("支付宝.jpg")
        pay_label2 = QLabel()
        pay_label2.setPixmap(pay_pixmap2.scaled(250, 300, Qt.AspectRatioMode.KeepAspectRatio,
                                                Qt.TransformationMode.SmoothTransformation))
        pay_label2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image_layout.addWidget(pay_label2)

        main_layout.addLayout(image_layout)

        # 关闭按钮
        btn_close = QPushButton("关闭")
        btn_close.setStyleSheet(
            "padding: 8px 20px; font-size: 14px; background-color: #0078d4; color: white; border-radius: 6px;"
        )
        btn_close.clicked.connect(dialog.accept)
        main_layout.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignCenter)

        dialog.setLayout(main_layout)
        dialog.exec()


# 运行程序
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon("haunsou.ico"))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
