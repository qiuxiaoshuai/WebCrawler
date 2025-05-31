import sys
import requests
from lxml import html
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import concurrent.futures
import time
import random
import csv
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton, QTextEdit, QVBoxLayout,
    QHBoxLayout, QMessageBox, QFileDialog, QTableWidget, QTableWidgetItem
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/114.0.0.0 Safari/537.36"
}

class MovieSpiderThread(QThread):
    progress_signal = pyqtSignal(str)
    result_signal = pyqtSignal(list)
    finished_signal = pyqtSignal()

    def __init__(self, max_pages):
        super().__init__()
        self.max_pages = max_pages
        self.is_running = True

    def stop(self):
        self.is_running = False

    def get_detail_info(self, detail_url, retries=1):
        for attempt in range(retries + 1):
            if not self.is_running:
                return ("停止爬取",) * 7
            try:
                resp = requests.get(detail_url, headers=HEADERS, timeout=10)
                resp.raise_for_status()
                tree = html.fromstring(resp.text)

                title = tree.xpath('//h2[@class="m-b-sm"]/text()')
                title_text = title[0].strip() if title else "无标题"

                score = tree.xpath('//p[contains(@class,"score")]/text()')
                score_text = score[0].strip() if score else "无评分"

                plot = tree.xpath('//div[contains(@class,"drama")]/p/text()')
                plot_text = plot[0].strip() if plot else "无剧情简介"

                area = tree.xpath('//div[@class="m-v-sm info"][1]/span[1]/text()')
                area_text = area[0].strip() if area else "无地点"

                duration = tree.xpath('//div[@class="m-v-sm info"][1]/span[3]/text()')
                duration_text = duration[0].strip() if duration else "无时长"

                release = tree.xpath('//div[@class="m-v-sm info"][2]/span[1]/text()')
                release_text = release[0].strip() if release else "无上映时间"

                return (title_text, score_text, plot_text, area_text, duration_text, release_text, detail_url)
            except Exception as e:
                if attempt < retries:
                    time.sleep(1)
                else:
                    return ("请求失败", "请求失败", f"请求失败: {e}", "请求失败", "请求失败", "请求失败", detail_url)

    def clean_text(self, text):
        return text.replace('\n', ' ').replace('\r', ' ').replace(',', '，').strip()

    def run(self):
        base_url = "https://ssr1.scrape.center"
        movie_details = []

        # 初始化selenium webdriver
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        driver = webdriver.Chrome(options=options)

        try:
            for page in range(1, self.max_pages + 1):
                if not self.is_running:
                    self.progress_signal.emit("爬取已停止")
                    break
                url = f"{base_url}/page/{page}"
                self.progress_signal.emit(f"正在爬取第 {page} 页: {url}")
                driver.get(url)
                time.sleep(random.uniform(0.1, 2))

                tree = html.fromstring(driver.page_source)
                movie_cards = tree.xpath('//div[@class="el-card__body"]/div[@class="el-row"]')

                if not movie_cards:
                    self.progress_signal.emit(f"第 {page} 页没有找到电影列表，可能已到最后一页。")
                    break

                for card in movie_cards:
                    title = card.xpath('.//h2/text()')
                    title_text = self.clean_text(title[0]) if title else "无标题"
                    detail_links = card.xpath('.//a[@class="name"]/@href')
                    if detail_links:
                        detail_url = base_url + detail_links[0]
                        movie_details.append((title_text, detail_url))
                self.progress_signal.emit(f"第 {page} 页共发现 {len(movie_cards)} 部电影。")

        except Exception as e:
            self.progress_signal.emit(f"列表页爬取出错: {e}")
        finally:
            driver.quit()

        self.progress_signal.emit(f"\n共收集到 {len(movie_details)} 部电影，开始抓取详细信息...")

        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            future_to_movie = {executor.submit(self.get_detail_info, url): (title, url) for title, url in movie_details}

            for i, future in enumerate(concurrent.futures.as_completed(future_to_movie), 1):
                if not self.is_running:
                    self.progress_signal.emit("爬取已停止")
                    break
                origin_title, url = future_to_movie[future]
                try:
                    title, score, plot, area, duration, release, detail_url = future.result()
                    title = self.clean_text(title)
                    score = self.clean_text(score)
                    plot = self.clean_text(plot)
                    area = self.clean_text(area)
                    duration = self.clean_text(duration)
                    release = self.clean_text(release)

                    self.progress_signal.emit(f"[{i}/{len(movie_details)}] 电影名称: {title}")
                    results.append((title, score, area, duration, release, detail_url, plot))
                except Exception as e:
                    self.progress_signal.emit(f"[{i}/{len(movie_details)}] 电影: {origin_title} 抓取失败: {e}")
                    results.append((origin_title, "抓取失败", "抓取失败", "抓取失败", "抓取失败", url, "抓取失败"))

                time.sleep(random.uniform(0.1, 0.5))

        self.result_signal.emit(results)
        self.finished_signal.emit()


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🎬 电影爬取器 - 小帅")
        self.resize(900, 600)
        self.setup_ui()
        self.spider_thread = None
        self.movie_results = []

    def setup_ui(self):
        layout = QVBoxLayout()

        # 输入区
        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("请输入要爬取的页数（1-10推荐）："))
        self.page_input = QLineEdit()
        self.page_input.setFixedWidth(50)
        self.page_input.setText("1")
        input_layout.addWidget(self.page_input)

        self.start_btn = QPushButton("开始爬取")
        self.start_btn.clicked.connect(self.start_spider)
        input_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("停止爬取")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_spider)
        input_layout.addWidget(self.stop_btn)

        layout.addLayout(input_layout)

        # 日志显示
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text, stretch=2)

        # 表格显示
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["电影标题", "评分", "地点", "时长", "上映时间", "详情页链接", "剧情简介"])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, stretch=3)

        # 保存按钮
        self.save_btn = QPushButton("保存为 CSV")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self.save_csv)
        layout.addWidget(self.save_btn)

        self.setLayout(layout)

    def log(self, message):
        self.log_text.append(message)

    def start_spider(self):
        try:
            max_pages = int(self.page_input.text())
            if max_pages < 1:
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, "输入错误", "请输入有效的页数（大于0的整数）")
            return

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.table.setRowCount(0)
        self.movie_results = []
        self.log_text.clear()

        self.spider_thread = MovieSpiderThread(max_pages)
        self.spider_thread.progress_signal.connect(self.log)
        self.spider_thread.result_signal.connect(self.show_results)
        self.spider_thread.finished_signal.connect(self.spider_finished)
        self.spider_thread.start()

    def stop_spider(self):
        if self.spider_thread:
            self.spider_thread.stop()
            self.stop_btn.setEnabled(False)
            self.log("停止爬取请求已发送，稍等...")

    def show_results(self, results):
        self.movie_results = results
        self.table.setRowCount(len(results))
        for row, (title, score, area, duration, release, url, plot) in enumerate(results):
            self.table.setItem(row, 0, QTableWidgetItem(title))
            self.table.setItem(row, 1, QTableWidgetItem(score))
            self.table.setItem(row, 2, QTableWidgetItem(area))
            self.table.setItem(row, 3, QTableWidgetItem(duration))
            self.table.setItem(row, 4, QTableWidgetItem(release))
            self.table.setItem(row, 5, QTableWidgetItem(url))
            self.table.setItem(row, 6, QTableWidgetItem(plot))

    def spider_finished(self):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.save_btn.setEnabled(True)
        self.log("爬取完成！")

    def save_csv(self):
        if not self.movie_results:
            QMessageBox.warning(self, "无数据", "没有数据可保存！")
            return

        path, _ = QFileDialog.getSaveFileName(self, "保存CSV文件", "", "CSV文件 (*.csv)")
        if path:
            try:
                with open(path, mode='w', encoding='utf-8', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(["电影标题", "评分", "地点", "时长", "上映时间", "详情页链接", "剧情简介"])
                    writer.writerows(self.movie_results)
                QMessageBox.information(self, "保存成功", f"数据已保存到 {path}")
            except Exception as e:
                QMessageBox.critical(self, "保存失败", f"保存CSV文件失败: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
