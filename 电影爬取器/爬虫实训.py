import time
import random
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, WebDriverException


# 解决 matplotlib 中文显示问题
plt.rcParams['font.sans-serif'] = ['SimHei']  # 黑体
plt.rcParams['axes.unicode_minus'] = False    # 负号正常显示

# ========== 1. 设置浏览器选项 ==========
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
        print("❌ 启动浏览器失败:", e)
        return None
    return driver

# ========== 2. 爬取景点信息 ==========
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn, TimeRemainingColumn

from tqdm import tqdm  # 添加 tqdm 进度条

def scrape_sight_data(max_pages=10):
    driver = init_driver()
    if driver is None:
        return pd.DataFrame()

    data = []

    print(f"\n📊 正在爬取页面进度:")
    for page in tqdm(range(1, max_pages + 1), desc="📡 正在爬取", unit="页", ncols=80):
        url = f"https://you.ctrip.com/sightlist/china110000/s0-p{page}.html"
        try:
            driver.get(url)
            time.sleep(random.uniform(0.1, 0.5))  # 模拟反爬机制延迟
        except Exception as e:
            print(f"⚠️ 第 {page} 页加载失败: {e}")
            break

        sights = driver.find_elements(By.CSS_SELECTOR, "div.rdetailbox")
        if not sights:
            print(f"❗ 第 {page} 页未找到景点信息，提前终止")
            break

        for sight in sights:
            try:
                name = sight.find_element(By.CSS_SELECTOR, "dt a").text.strip()
                hot_score = sight.find_element(By.CSS_SELECTOR, "a.hot_score b.hot_score_number").text.strip()
                rating = sight.find_element(By.CSS_SELECTOR, "ul.r_comment li a.score strong").text.strip()
                comment_text = sight.find_element(By.CSS_SELECTOR, "ul.r_comment li a.recomment").text.strip()
                comment_num = comment_text.replace("(", "").replace(")", "").replace("条点评", "").replace(",",
                                                                                                           "").strip()

                data.append({
                    "景点名": name,
                    "热度": hot_score,
                    "评分": rating,
                    "点评数": comment_num
                })
            except NoSuchElementException:
                # 只打印简短提示，不显示堆栈
                print(f"⚠️ 第 {page} 页部分元素未找到，跳过该条")
                continue
            except Exception as e:
                # 其它异常可选择打印或忽略
                print(f"⚠️ 第 {page} 页解析失败: {e}")
                continue

    driver.quit()
    return pd.DataFrame(data)


# ========== 3. 清洗数据 ==========
def clean_data(df):
    # 转换数值列，错误转为 NaN
    df['热度'] = pd.to_numeric(df['热度'], errors='coerce')
    df['评分'] = pd.to_numeric(df['评分'], errors='coerce')
    df['点评数'] = pd.to_numeric(df['点评数'], errors='coerce')

    # 删除含有NaN的行
    df_clean = df.dropna().reset_index(drop=True)
    return df_clean


# ========== 4. 绘制评分分布图 ==========
# 评分分布图，带数量标注
def plot_rating_distribution(df):
    plt.figure(figsize=(10, 6))
    counts, bins, patches = plt.hist(df["评分"], bins=15, color='skyblue', edgecolor='black')
    plt.title("景点评分分布图")
    plt.xlabel("评分")
    plt.ylabel("景点数量")
    plt.grid(True, linestyle='--', alpha=0.7)

    for count, patch in zip(counts, patches):
        if count > 0:
            plt.text(patch.get_x() + patch.get_width() / 2, count, int(count),
                     ha='center', va='bottom', fontsize=9, color='black')

    plt.tight_layout()
    plt.show()

# 点评最多前10景点，带数量标注
def plot_top10_comments(df):
    top10 = df.sort_values(by="点评数", ascending=False).head(10)
    plt.figure(figsize=(12, 6))
    bars = plt.bar(top10["景点名"], top10["点评数"], color='orange')
    plt.title("点评最多的前10个景点")
    plt.xlabel("景点名")
    plt.ylabel("点评数")
    plt.xticks(rotation=45, ha="right")

    for bar, val in zip(bars, top10["点评数"]):
        plt.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), f"{int(val)}",
                 ha='center', va='bottom', fontsize=9)

    plt.tight_layout()
    plt.show()

# 热度分布图，带数量标注
def plot_hot_score_distribution(df):
    plt.figure(figsize=(10, 6))
    counts, bins, patches = plt.hist(df["热度"], bins=15, color='lightgreen', edgecolor='black')
    plt.title("景点热度分布图")
    plt.xlabel("热度")
    plt.ylabel("景点数量")
    plt.grid(True, linestyle='--', alpha=0.7)

    for count, patch in zip(counts, patches):
        if count > 0:
            plt.text(patch.get_x() + patch.get_width() / 2, count, int(count),
                     ha='center', va='bottom', fontsize=9, color='black')

    plt.tight_layout()
    plt.show()

# 点评数最多景点评分，带点评数标注
def plot_top_rated_and_commented(df, top_n=10):
    top_df = df.sort_values(by="点评数", ascending=False).head(top_n)
    plt.figure(figsize=(12, 6))
    bars = plt.bar(top_df["景点名"], top_df["评分"], color='coral', alpha=0.8)
    plt.title(f"点评数最多的前{top_n}景点评分")
    plt.xlabel("景点名")
    plt.ylabel("评分")
    plt.ylim(0, 5)
    plt.xticks(rotation=45, ha='right')

    for bar, comment_num in zip(bars, top_df["点评数"]):
        plt.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.1, f"{int(comment_num):,}",
                 ha='center', va='bottom', fontsize=8)
    plt.tight_layout()
    plt.show()

# 评分箱型图
def plot_rating_boxplot(df):
    plt.figure(figsize=(8, 5))
    plt.boxplot(df["评分"], patch_artist=True, boxprops=dict(facecolor='lightblue'))
    plt.title("景点评分箱型图")
    plt.ylabel("评分")
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.tight_layout()
    plt.show()

# 评分与点评数关系散点图
def plot_rating_vs_comments(df):
    plt.figure(figsize=(10, 6))
    plt.scatter(df["点评数"], df["评分"], alpha=0.6, c=np.log1p(df["热度"]), cmap='viridis')
    plt.colorbar(label="热度（对数刻度）")
    plt.title("评分与点评数关系散点图")
    plt.xlabel("点评数")
    plt.ylabel("评分")
    plt.grid(True, linestyle='--', alpha=0.5)
    plt.tight_layout()
    plt.show()

# 不同评分段数量条形图，带数量标注
def plot_rating_counts(df):
    bins = [0, 2, 3, 4, 4.5, 5]
    labels = ['<2', '2-3', '3-4', '4-4.5', '4.5-5']
    df['评分段'] = pd.cut(df['评分'], bins=bins, labels=labels, right=False)
    rating_counts = df['评分段'].value_counts().sort_index()

    plt.figure(figsize=(8, 5))
    bars = rating_counts.plot(kind='bar', color='mediumpurple', edgecolor='black')

    for i, val in enumerate(rating_counts):
        plt.text(i, val, int(val), ha='center', va='bottom', fontsize=9)

    plt.title("不同评分段的景点数量")
    plt.xlabel("评分区间")
    plt.ylabel("景点数量")
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.tight_layout()
    plt.show()

# 热度分布与正态分布拟合，带标注
def plot_hot_score_distribution_with_fit(df):
    plt.figure(figsize=(10, 6))
    data = df["热度"].dropna()

    counts, bins, patches = plt.hist(data, bins=15, density=True, alpha=0.6, color='lightgreen', edgecolor='black', label='实际热度分布')

    mu, sigma = np.mean(data), np.std(data)
    x = np.linspace(min(data), max(data), 100)
    y = (1 / (sigma * np.sqrt(2 * np.pi))) * np.exp(- (x - mu) ** 2 / (2 * sigma ** 2))
    plt.plot(x, y, 'r--', label=f'正态分布拟合: μ={mu:.2f}, σ={sigma:.2f}')

    plt.title("热度分布与正态分布拟合")
    plt.xlabel("热度")
    plt.ylabel("概率密度")
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.tight_layout()
    plt.show()

# ========== 8. 主流程 ==========
def main(max_pages=10):
    raw_df = scrape_sight_data(max_pages=max_pages)
    if raw_df.empty:
        print("⚠️ 未抓取到任何数据，程序结束")
        return

    raw_df.to_csv("selenium_景点原始数据.csv", index=False, encoding="utf-8-sig")
    print(f"✅ 原始数据保存完成，共 {len(raw_df)} 条记录")

    clean_df = clean_data(raw_df)
    print(f"✅ 数据清洗完成，剩余 {len(clean_df)} 条有效记录")
    clean_df.to_csv("selenium_景点清洗后数据.csv", index=False, encoding="utf-8-sig")
    print("✅ 清洗后数据保存完成")

    # 绘图分析
    plot_rating_distribution(clean_df)
    plot_top10_comments(clean_df)
    plot_hot_score_distribution(clean_df)
    plot_top_rated_and_commented(clean_df)
    plot_rating_boxplot(clean_df)
    plot_rating_vs_comments(clean_df)
    plot_rating_counts(clean_df)
    plot_hot_score_distribution_with_fit(clean_df)
if __name__ == "__main__":
    try:
        pages = int(input("请输入要爬取的页数（建议不超过50页）："))
        if pages <= 0:
            raise ValueError
    except ValueError:
        print("❌ 输入无效，已使用默认值：10")
        pages = 10

    main(max_pages=pages)
