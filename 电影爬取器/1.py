import requests
from lxml import html
from urllib.parse import urljoin
# 发送 GET 请求
url = "http://books.toscrape.com/"
response = requests.get(url)
current_url = url
# 输出网页源码（前500字符示例）
print("网页源码（部分）：")
print(response.text[:500])  # 为避免控制台拥挤，仅打印前500个字符
print("\n" + "="*80 + "\n")

# 输出响应头部信息
print("响应头部信息：")
for key, value in response.headers.items():
    print(f"{key}: {value}")
print("\n" + "="*80 + "\n")

# 输出请求状态码
print("请求状态码：")
print(response.status_code)
print("\n" + "="*80 + "\n")

# 输出Cookies
print("Cookies：")
for cookie in response.cookies:
    print(f"{cookie.name}: {cookie.value}")
print("\n" + "="*80 + "\n")

# 使用lxml解析网页
tree = html.fromstring(response.text)

current_page = 1
max_pages = int(input("请输入要爬取的页数（例如 3）："))
while current_page <= max_pages:
    response = requests.get(current_url)
    tree = html.fromstring(response.text)

    print(f"\n==== 正在爬取第 {current_page} 页 ====")

    # 提取书名和价格
    book_titles = tree.xpath('//article[@class="product_pod"]/h3/a/@title')
    book_prices = tree.xpath('//article[@class="product_pod"]//p[@class="price_color"]/text()')

    for title, price in zip(book_titles, book_prices):
        print(f"《{title}》 - 价格：{price}")

    # 查找下一页链接
    next_page = tree.xpath('//li[@class="next"]/a/@href')
    if next_page:
        next_href = next_page[0]
        current_url = urljoin(current_url, next_href)
        current_page += 1
    else:
        print("\n✅ 已经到达最后一页，提前结束爬取。")
        break

print("\n🎉 爬取完成。")