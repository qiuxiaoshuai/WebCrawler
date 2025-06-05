import sys
import os
import threading
import time
import random
import pandas as pd
import numpy as np
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSpinBox,
    QFileDialog, QTabWidget, QMessageBox, QProgressBar, QTableWidget, QTableWidgetItem,
    QHeaderView, QComboBox, QCheckBox, QTextEdit
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QIcon, QAction,QTextCursor

import matplotlib
matplotlib.use('QtAgg')  # 改为 Qt6 兼容的后端
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, WebDriverException

# 解决 matplotlib 中文显示问题
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

class ScraperSignals(QObject):
    progress = pyqtSignal(int)
    message = pyqtSignal(str)
    finished = pyqtSignal(pd.DataFrame)

def init_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-blink-features=AutomationControlled")
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64)...",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)...",
        "Mozilla/5.0 (X11; Linux x86_64)..."
    ]
    options.add_argument(f"user-agent={random.choice(user_agents)}")
    try:
        driver = webdriver.Chrome(options=options)
    except WebDriverException as e:
        return None
    return driver

def scrape_sight_data(max_pages=10, signals=None):
    driver = init_driver()
    if driver is None:
        if signals:
            signals.message.emit("❌ 启动浏览器失败，请检查ChromeDriver！")
            signals.finished.emit(pd.DataFrame())
        return pd.DataFrame()

    data = []
    for page in range(1, max_pages + 1):
        url = f"https://you.ctrip.com/sightlist/china110000/s0-p{page}.html"
        try:
            driver.get(url)
            time.sleep(random.uniform(0.5, 1.5))
        except Exception as e:
            if signals:
                signals.message.emit(f"⚠️ 第{page}页加载失败: {e}")
            break

        sights = driver.find_elements(By.CSS_SELECTOR, "div.rdetailbox")
        if not sights:
            if signals:
                signals.message.emit(f"❗ 第{page}页未找到景点信息，提前终止")
            break

        for sight in sights:
            try:
                name = sight.find_element(By.CSS_SELECTOR, "dt a").text.strip()
                hot_score = sight.find_element(By.CSS_SELECTOR, "a.hot_score b.hot_score_number").text.strip()
                rating = sight.find_element(By.CSS_SELECTOR, "ul.r_comment li a.score strong").text.strip()
                comment_text = sight.find_element(By.CSS_SELECTOR, "ul.r_comment li a.recomment").text.strip()
                comment_num = comment_text.replace("(", "").replace(")", "").replace("条点评", "").replace(",", "").strip()
                data.append({
                    "景点名": name,
                    "热度": hot_score,
                    "评分": rating,
                    "点评数": comment_num
                })
            except NoSuchElementException:
                continue
            except Exception:
                continue
        if signals:
            signals.progress.emit(int(page / max_pages * 100))
    driver.quit()
    result_df = pd.DataFrame(data)
    if signals:
        signals.finished.emit(result_df)
    return result_df

def clean_data(df):
    df['热度'] = pd.to_numeric(df['热度'], errors='coerce')
    df['评分'] = pd.to_numeric(df['评分'], errors='coerce')
    df['点评数'] = pd.to_numeric(df['点评数'], errors='coerce')
    df_clean = df.dropna().reset_index(drop=True)
    return df_clean

# --- Matplotlib Figure Widget ---
class MplCanvas(FigureCanvas):
    def __init__(self, width=5, height=4, dpi=100):
        self.fig, self.ax = plt.subplots(figsize=(width, height), dpi=dpi)
        super().__init__(self.fig)

# --- 主要GUI类 ---
class SightGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("中国景点数据采集与分析")
        self.setWindowIcon(QIcon())
        self.resize(1100, 700)
        self.df_raw = None
        self.df_clean = None

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # 顶部操作区
        top_layout = QHBoxLayout()
        self.page_label = QLabel("要爬取页数：")
        self.page_spin = QSpinBox()
        self.page_spin.setRange(1, 100)
        self.page_spin.setValue(10)
        self.start_btn = QPushButton("开始采集")
        self.save_raw_btn = QPushButton("保存原始数据")
        self.save_clean_btn = QPushButton("保存清洗后数据")
        self.save_raw_btn.setEnabled(False)
        self.save_clean_btn.setEnabled(False)
        top_layout.addWidget(self.page_label)
        top_layout.addWidget(self.page_spin)
        top_layout.addWidget(self.start_btn)
        top_layout.addWidget(self.save_raw_btn)
        top_layout.addWidget(self.save_clean_btn)
        top_layout.addStretch()
        layout.addLayout(top_layout)

        # 进度区
        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setFormat("%p%")
        layout.addWidget(self.progress)

        # 消息区
        self.status_box = QTextEdit()
        self.status_box.setReadOnly(True)
        layout.addWidget(self.status_box, stretch=1)

        # 标签页区
        self.tabs = QTabWidget()
        self.tab_table = QWidget()
        self.tab_table_layout = QVBoxLayout(self.tab_table)
        self.table = QTableWidget()
        self.tab_table_layout.addWidget(self.table)
        self.tabs.addTab(self.tab_table, "数据表格")

        self.tab_plots = QWidget()
        self.tab_plots_layout = QVBoxLayout(self.tab_plots)
        self.plot_selector = QComboBox()
        self.plot_selector.addItems([
            "评分分布图",
            "点评最多前10景点",
            "热度分布图",
            "点评最多景点评分",
            "评分箱型图",
            "评分与点评数关系散点图",
            "不同评分段数量条形图",
            "热度分布与正态分布拟合"
        ])
        self.plot_btn = QPushButton("显示图表")
        plot_top = QHBoxLayout()
        plot_top.addWidget(QLabel("选择分析图表："))
        plot_top.addWidget(self.plot_selector)
        plot_top.addWidget(self.plot_btn)
        plot_top.addStretch()
        self.tab_plots_layout.addLayout(plot_top)
        self.canvas = MplCanvas(width=10, height=5, dpi=100)
        self.tab_plots_layout.addWidget(self.canvas)
        self.tabs.addTab(self.tab_plots, "数据可视化")
        layout.addWidget(self.tabs, stretch=2)

        # 功能扩展（筛选区）
        filter_layout = QHBoxLayout()

        self.filter_rating_checkbox = QCheckBox("只显示评分>4的景点")
        self.filter_hot_checkbox = QCheckBox("只显示热度>9.0的景点")
        # 新增热度区间筛选控件
        self.filter_hot_label = QLabel("热度区间最小值")
        self.filter_hot_min_spin = QSpinBox()
        self.filter_hot_min_spin.setRange(0, 10)
        self.filter_hot_min_spin.setValue(0)

        self.filter_hot_max_label = QLabel("最大值")
        self.filter_hot_max_spin = QSpinBox()
        self.filter_hot_max_spin.setRange(0, 10)
        self.filter_hot_max_spin.setValue(10)

        # 添加到筛选布局里
        filter_layout.addWidget(self.filter_hot_label)
        filter_layout.addWidget(self.filter_hot_min_spin)
        filter_layout.addWidget(self.filter_hot_max_label)
        filter_layout.addWidget(self.filter_hot_max_spin)

        # 新增：点评数筛选
        self.filter_comment_checkbox = QCheckBox("只显示点评数大于")
        self.filter_comment_spin = QSpinBox()
        self.filter_comment_spin.setRange(0, 100000)
        self.filter_comment_spin.setValue(100)

        # 新增：景点名关键字筛选
        self.filter_name_checkbox = QCheckBox("景点名包含关键字")
        self.filter_name_edit = QTextEdit()
        self.filter_name_edit.setMaximumHeight(30)

        # 新增：评分区间筛选
        self.filter_rating_min_label = QLabel("评分区间最小值")
        self.filter_rating_min_spin = QSpinBox()
        self.filter_rating_min_spin.setRange(0, 5)
        self.filter_rating_min_spin.setValue(0)
        self.filter_rating_max_label = QLabel("最大值")
        self.filter_rating_max_spin = QSpinBox()
        self.filter_rating_max_spin.setRange(0, 5)
        self.filter_rating_max_spin.setValue(5)

        # 添加控件到布局
        filter_layout.addWidget(QLabel("筛选："))
        filter_layout.addWidget(self.filter_rating_checkbox)
        # filter_layout.addWidget(self.filter_hot_checkbox)
        filter_layout.addWidget(self.filter_comment_checkbox)
        filter_layout.addWidget(self.filter_comment_spin)
        filter_layout.addWidget(self.filter_name_checkbox)
        filter_layout.addWidget(self.filter_name_edit)
        filter_layout.addWidget(self.filter_rating_min_label)
        filter_layout.addWidget(self.filter_rating_min_spin)
        filter_layout.addWidget(self.filter_rating_max_label)
        filter_layout.addWidget(self.filter_rating_max_spin)

        self.reset_filter_btn = QPushButton("重置筛选")
        filter_layout.addWidget(self.reset_filter_btn)
        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        # filter_layout = QHBoxLayout()
        # self.filter_rating_checkbox = QCheckBox("只显示评分>4的景点")
        # self.filter_hot_checkbox = QCheckBox("只显示热度>9.0的景点")
        # self.reset_filter_btn = QPushButton("重置筛选")
        # filter_layout.addWidget(QLabel("筛选："))
        # filter_layout.addWidget(self.filter_rating_checkbox)
        # filter_layout.addWidget(self.filter_hot_checkbox)
        # filter_layout.addWidget(self.reset_filter_btn)
        # filter_layout.addStretch()
        # layout.addLayout(filter_layout)
        #
        self.setLayout(layout)
        self.connect_signals()

    def connect_signals(self):
        self.start_btn.clicked.connect(self.on_start)
        self.save_raw_btn.clicked.connect(self.save_raw_data)
        self.save_clean_btn.clicked.connect(self.save_clean_data)
        self.plot_btn.clicked.connect(self.show_plot)
        self.filter_rating_checkbox.stateChanged.connect(self.update_table)
        # self.filter_hot_checkbox.stateChanged.connect(self.update_table)
        self.filter_hot_min_spin.valueChanged.connect(self.update_table)
        self.filter_hot_max_spin.valueChanged.connect(self.update_table)

        self.reset_filter_btn.clicked.connect(self.reset_filters)
        #新
        self.filter_comment_checkbox.stateChanged.connect(self.update_table)
        self.filter_comment_spin.valueChanged.connect(self.update_table)
        self.filter_name_checkbox.stateChanged.connect(self.update_table)
        self.filter_name_edit.textChanged.connect(self.update_table)
        self.filter_rating_min_spin.valueChanged.connect(self.update_table)
        self.filter_rating_max_spin.valueChanged.connect(self.update_table)

    def log(self, msg):
        self.status_box.append(msg)
        self.status_box.moveCursor(QTextCursor.MoveOperation.End)

    def on_start(self):
        self.start_btn.setEnabled(False)
        self.save_raw_btn.setEnabled(False)
        self.save_clean_btn.setEnabled(False)
        self.progress.setValue(0)
        self.status_box.clear()
        max_pages = self.page_spin.value()
        self.log(f"🚀 开始采集{max_pages}页景点信息...")
        self.df_raw = None
        self.df_clean = None
        self.update_table()
        self.canvas.ax.clear()
        self.canvas.draw()

        # 多线程采集
        self.scraper_signals = ScraperSignals()
        self.scraper_signals.progress.connect(self.progress.setValue)
        self.scraper_signals.message.connect(self.log)
        self.scraper_signals.finished.connect(self.on_scrape_finished)
        threading.Thread(
            target=scrape_sight_data,
            args=(max_pages, self.scraper_signals),
            daemon=True
        ).start()

    def on_scrape_finished(self, df):
        if df.empty:
            self.log("❌ 未采集到数据，请重试或检查网络/驱动")
            self.start_btn.setEnabled(True)
            return
        self.df_raw = df
        self.df_clean = clean_data(df)
        self.log(f"✅ 采集完成，共{len(self.df_raw)}条记录。有效数据{len(self.df_clean)}条。")
        self.save_raw_btn.setEnabled(True)
        self.save_clean_btn.setEnabled(True)
        self.update_table()
        self.start_btn.setEnabled(True)

    def update_table(self):
        df = self.df_clean if self.df_clean is not None else None
        if df is None or df.empty:
            self.table.setRowCount(0)
            self.table.setColumnCount(0)
            return

        filtered = df.copy()

        if self.filter_rating_checkbox.isChecked():
            filtered = filtered[filtered["评分"] > 4]

        if self.filter_hot_checkbox.isChecked():
            # filtered = filtered[filtered["热度"] > 9.0]
            min_hot = self.filter_hot_min_spin.value()
            max_hot = self.filter_hot_max_spin.value()
            filtered = filtered[(filtered["热度"] >= min_hot) & (filtered["热度"] <= max_hot)]

        if self.filter_comment_checkbox.isChecked():
            val = self.filter_comment_spin.value()
            filtered = filtered[filtered["点评数"] > val]

        if self.filter_name_checkbox.isChecked():
            keyword = self.filter_name_edit.toPlainText().strip()
            if keyword:
                filtered = filtered[filtered["景点名"].str.contains(keyword, case=False, na=False)]

        # 评分区间筛选
        min_rating = self.filter_rating_min_spin.value()
        max_rating = self.filter_rating_max_spin.value()
        filtered = filtered[(filtered["评分"] >= min_rating) & (filtered["评分"] <= max_rating)]

        filtered = filtered.reset_index(drop=True)

        self.table.setColumnCount(len(filtered.columns))
        self.table.setRowCount(len(filtered))
        self.table.setHorizontalHeaderLabels(filtered.columns)
        for row in range(len(filtered)):
            for col in range(len(filtered.columns)):
                self.table.setItem(row, col, QTableWidgetItem(str(filtered.iat[row, col])))
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

    # def update_table(self):
    #     df = self.df_clean if self.df_clean is not None else None
    #     if df is None or df.empty:
    #         self.table.setRowCount(0)
    #         self.table.setColumnCount(0)
    #         return
    #
    #     filtered = df.copy()
    #     if self.filter_rating_checkbox.isChecked():
    #         filtered = filtered[filtered["评分"] > 4]
    #     if self.filter_hot_checkbox.isChecked():
    #         filtered = filtered[filtered["热度"] > 9.0]
    #     filtered = filtered.reset_index(drop=True)
    #
    #     self.table.setColumnCount(len(filtered.columns))
    #     self.table.setRowCount(len(filtered))
    #     self.table.setHorizontalHeaderLabels(filtered.columns)
    #     for row in range(len(filtered)):
    #         for col in range(len(filtered.columns)):
    #             self.table.setItem(row, col, QTableWidgetItem(str(filtered.iat[row, col])))
    #     self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

    def reset_filters(self):
        self.filter_rating_checkbox.setChecked(False)
        self.filter_hot_checkbox.setChecked(False)
        self.filter_comment_checkbox.setChecked(False)
        self.filter_comment_spin.setValue(100)
        self.filter_name_checkbox.setChecked(False)
        self.filter_name_edit.clear()
        self.filter_rating_min_spin.setValue(0)
        self.filter_rating_max_spin.setValue(5)
        self.filter_hot_min_spin.setValue(0)
        self.filter_hot_max_spin.setValue(100)

        self.update_table()

    def save_raw_data(self):
        if self.df_raw is not None:
            fname, _ = QFileDialog.getSaveFileName(self, "保存原始数据", "selenium_景点原始数据.csv", "CSV Files (*.csv)")
            if fname:
                self.df_raw.to_csv(fname, index=False, encoding="utf-8-sig")
                self.log(f"💾 原始数据已保存到: {fname}")

    def save_clean_data(self):
        if self.df_clean is not None:
            fname, _ = QFileDialog.getSaveFileName(self, "保存清洗后数据", "selenium_景点清洗后数据.csv", "CSV Files (*.csv)")
            if fname:
                self.df_clean.to_csv(fname, index=False, encoding="utf-8-sig")
                self.log(f"💾 清洗后数据已保存到: {fname}")

    def show_plot(self):
        df = self.df_clean
        if df is None or df.empty:
            QMessageBox.warning(self, "暂无数据", "请先采集并清洗数据！")
            return

        choice = self.plot_selector.currentText()

        # 清除旧图像
        self.canvas.fig.clf()

        # 添加新的子图
        ax = self.canvas.fig.add_subplot(111)

        # ❌ 移除 plt.sca(ax)，这是 pyplot 专用函数，不能用于嵌入式绘图

        # 绘图逻辑
        if choice == "评分分布图":
            self._plot_rating_distribution(df, ax)
        elif choice == "点评最多前10景点":
            self._plot_top10_comments(df, ax)
        elif choice == "热度分布图":
            self._plot_hot_score_distribution(df, ax)
        elif choice == "点评最多景点评分":
            self._plot_top_rated_and_commented(df, ax)
        elif choice == "评分箱型图":
            self._plot_rating_boxplot(df, ax)
        elif choice == "评分与点评数关系散点图":
            self._plot_rating_vs_comments(df, ax)
        elif choice == "不同评分段数量条形图":
            self._plot_rating_counts(df, ax)
        elif choice == "热度分布与正态分布拟合":
            self._plot_hot_score_distribution_with_fit(df, ax)

        # 刷新画布显示
        self.canvas.draw()

    # --- 各类绘图 ---
    def _plot_rating_distribution(self, df, ax):
        counts, bins, patches = ax.hist(df["评分"], bins=15, color='skyblue', edgecolor='black')
        ax.set_title("景点评分分布图")
        ax.set_xlabel("评分")
        ax.set_ylabel("景点数量")
        ax.grid(True, linestyle='--', alpha=0.7)
        for count, patch in zip(counts, patches):
            if count > 0:
                ax.text(patch.get_x() + patch.get_width() / 2, count, int(count),
                        ha='center', va='bottom', fontsize=9, color='black')
        self.canvas.fig.tight_layout()

    def _plot_top10_comments(self, df, ax):
        top10 = df.sort_values(by="点评数", ascending=False).head(10)
        bars = ax.bar(top10["景点名"], top10["点评数"], color='orange')
        ax.set_title("点评最多的前10个景点")
        ax.set_xlabel("景点名")
        ax.set_ylabel("点评数")
        ax.set_xticklabels(top10["景点名"], rotation=45, ha="right")
        for bar, val in zip(bars, top10["点评数"]):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), f"{int(val)}",
                    ha='center', va='bottom', fontsize=9)
        self.canvas.fig.tight_layout()

    def _plot_hot_score_distribution(self, df, ax):
        counts, bins, patches = ax.hist(df["热度"], bins=15, color='lightgreen', edgecolor='black')
        ax.set_title("景点热度分布图")
        ax.set_xlabel("热度")
        ax.set_ylabel("景点数量")
        ax.grid(True, linestyle='--', alpha=0.7)
        for count, patch in zip(counts, patches):
            if count > 0:
                ax.text(patch.get_x() + patch.get_width() / 2, count, int(count),
                        ha='center', va='bottom', fontsize=9, color='black')
        self.canvas.fig.tight_layout()

    def _plot_top_rated_and_commented(self, df, ax, top_n=10):
        top_df = df.sort_values(by="点评数", ascending=False).head(top_n)
        bars = ax.bar(top_df["景点名"], top_df["评分"], color='coral', alpha=0.8)
        ax.set_title(f"点评数最多的前{top_n}景点评分")
        ax.set_xlabel("景点名")
        ax.set_ylabel("评分")
        ax.set_ylim(0, 5)
        ax.set_xticklabels(top_df["景点名"], rotation=45, ha='right')
        for bar, comment_num in zip(bars, top_df["点评数"]):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.1, f"{int(comment_num):,}",
                    ha='center', va='bottom', fontsize=8)
        self.canvas.fig.tight_layout()

    def _plot_rating_boxplot(self, df, ax):
        ax.boxplot(df["评分"], patch_artist=True, boxprops=dict(facecolor='lightblue'))
        ax.set_title("景点评分箱型图")
        ax.set_ylabel("评分")
        ax.grid(axis='y', linestyle='--', alpha=0.7)
        self.canvas.fig.tight_layout()

    def _plot_rating_vs_comments(self, df, ax):
        scatter = ax.scatter(df["点评数"], df["评分"], alpha=0.6, c=np.log1p(df["热度"]), cmap='viridis')
        cbar = self.canvas.fig.colorbar(scatter, ax=ax)
        cbar.set_label("热度（对数刻度）")
        ax.set_title("评分与点评数关系散点图")
        ax.set_xlabel("点评数")
        ax.set_ylabel("评分")
        ax.grid(True, linestyle='--', alpha=0.5)
        self.canvas.fig.tight_layout()

    def _plot_rating_counts(self, df, ax):
        bins = [0, 2, 3, 4, 4.5, 5]
        labels = ['<2', '2-3', '3-4', '4-4.5', '4.5-5']
        df['评分段'] = pd.cut(df['评分'], bins=bins, labels=labels, right=False)
        rating_counts = df['评分段'].value_counts().sort_index()
        bars = ax.bar(labels, rating_counts, color='mediumpurple', edgecolor='black')
        for i, val in enumerate(rating_counts):
            ax.text(i, val, int(val), ha='center', va='bottom', fontsize=9)
        ax.set_title("不同评分段的景点数量")
        ax.set_xlabel("评分区间")
        ax.set_ylabel("景点数量")
        ax.grid(axis='y', linestyle='--', alpha=0.7)
        self.canvas.fig.tight_layout()

    def _plot_hot_score_distribution_with_fit(self, df, ax):
        data = df["热度"].dropna()
        counts, bins, patches = ax.hist(data, bins=15, density=True, alpha=0.6, color='lightgreen', edgecolor='black', label='实际热度分布')
        mu, sigma = np.mean(data), np.std(data)
        x = np.linspace(min(data), max(data), 100)
        y = (1 / (sigma * np.sqrt(2 * np.pi))) * np.exp(- (x - mu) ** 2 / (2 * sigma ** 2))
        ax.plot(x, y, 'r--', label=f'正态分布拟合: μ={mu:.2f}, σ={sigma:.2f}')
        ax.set_title("热度分布与正态分布拟合")
        ax.set_xlabel("热度")
        ax.set_ylabel("概率密度")
        ax.legend()
        ax.grid(True, linestyle='--', alpha=0.7)
        self.canvas.fig.tight_layout()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = SightGUI()
    gui.show()
    sys.exit(app.exec())