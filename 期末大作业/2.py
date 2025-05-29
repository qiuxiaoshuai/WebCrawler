import requests
from lxml import html
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import concurrent.futures
import time
import random
import csv

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/114.0.0.0 Safari/537.36"
}


def get_detail_info(detail_url, retries=1):
    for attempt in range(retries + 1):
        try:
            resp = requests.get(detail_url, headers=HEADERS, timeout=10)
            resp.raise_for_status()
            tree = html.fromstring(resp.text)

            # 电影名称
            title = tree.xpath('//h2[@class="m-b-sm"]/text()')
            title_text = title[0].strip() if title else "无标题"

            # 评分
            score = tree.xpath('//p[contains(@class,"score")]/text()')
            score_text = score[0].strip() if score else "无评分"

            # 剧情简介
            plot = tree.xpath('//div[contains(@class,"drama")]/p/text()')
            plot_text = plot[0].strip() if plot else "无剧情简介"

            # 其他信息：地点、时长、上映时间
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


def clean_text(text):
    return text.replace('\n', ' ').replace('\r', ' ').replace(',', '，').strip()


def main():
    print("=== 电影爬取程序 ===")
    try:
        max_pages = int(input("请输入要爬取的页数（1-10推荐）："))
        if max_pages < 1:
            print("页数不能小于1，自动设置为1")
            max_pages = 1
    except ValueError:
        print("输入无效，默认爬取1页")
        max_pages = 1

    options = Options()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    driver = webdriver.Chrome(options=options)

    base_url = "https://ssr1.scrape.center"
    movie_details = []

    try:
        for page in range(1, max_pages + 1):
            url = f"{base_url}/page/{page}"
            print(f"正在爬取第 {page} 页: {url}")
            driver.get(url)
            time.sleep(random.uniform(0.1, 2))

            tree = html.fromstring(driver.page_source)
            movie_cards = tree.xpath('//div[@class="el-card__body"]/div[@class="el-row"]')

            if not movie_cards:
                print(f"第 {page} 页没有找到电影列表，可能已到最后一页。")
                break

            for card in movie_cards:
                title = card.xpath('.//h2/text()')
                title_text = clean_text(title[0]) if title else "无标题"
                detail_links = card.xpath('.//a[@class="name"]/@href')
                if detail_links:
                    detail_url = base_url + detail_links[0]
                    movie_details.append((title_text, detail_url))
            print(f"第 {page} 页共发现 {len(movie_cards)} 部电影。")

    except Exception as e:
        print("列表页爬取出错:", e)
    finally:
        driver.quit()

    print(f"\n共收集到 {len(movie_details)} 部电影，开始抓取详细信息...")

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        future_to_movie = {executor.submit(get_detail_info, url): (title, url) for title, url in movie_details}

        for i, future in enumerate(concurrent.futures.as_completed(future_to_movie), 1):
            origin_title, url = future_to_movie[future]
            try:
                title, score, plot, area, duration, release, detail_url = future.result()
                title = clean_text(title)
                score = clean_text(score)
                plot = clean_text(plot)
                area = clean_text(area)
                duration = clean_text(duration)
                release = clean_text(release)

                print(f"\n[{i}/{len(movie_details)}] 电影名称: {title}")
                print(f"评分: {score}")
                print(f"地点: {area}")
                print(f"时长: {duration}")
                print(f"上映时间: {release}")
                print(f"剧情简介: {plot[:150]}...")  # 只显示前150字符

                results.append((title, score, area, duration, release, detail_url, plot))
            except Exception as e:
                print(f"[{i}/{len(movie_details)}] 电影: {origin_title} 抓取失败: {e}")
                results.append((origin_title, "抓取失败", "抓取失败", "抓取失败", "抓取失败", url, "抓取失败"))

            time.sleep(random.uniform(0.1, 0.5))

    # 保存CSV
    csv_file = "movies_detailed.csv"
    try:
        with open(csv_file, mode='w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["电影标题", "评分", "地点", "时长", "上映时间", "详情页链接", "剧情简介"])
            writer.writerows(results)
        print(f"\n爬取完成，数据已保存到 {csv_file}")
    except Exception as e:
        print("保存CSV文件失败:", e)


if __name__ == "__main__":
    main()
