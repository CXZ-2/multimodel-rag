"""通用网页爬虫框架 + 站点适配器"""
from dataclasses import dataclass, field
from typing import Protocol
import httpx
from bs4 import BeautifulSoup


@dataclass
class CrawledPage:
    url: str
    title: str
    body_text: str
    raw_html: str = field(repr=False)
    published_date: str = ""


class SiteAdapter(Protocol):
    """站点适配器协议"""
    name: str
    base_url: str

    def discover_urls(self, limit: int = 20) -> list[str]: ...
    def parse_page(self, html: str, url: str) -> CrawledPage: ...


def create_client() -> httpx.Client:
    return httpx.Client(
        timeout=30,
        follow_redirects=True,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "zh-CN,zh;q=0.9",
        },
    )


def fetch_urls(client: httpx.Client, urls: list[str]) -> list[tuple[str, str]]:
    """批量抓取 URL，返回 [(url, html), ...]，跳过失败的"""
    results = []
    for url in urls:
        try:
            resp = client.get(url)
            if resp.status_code == 200 and resp.text:
                results.append((url, resp.text))
        except Exception:
            continue
    return results


class GovZhengceAdapter:
    """中国政府网-政策文件"""
    name = "gov_zhengce"
    base_url = "https://www.gov.cn"

    def discover_urls(self, limit: int = 20) -> list[str]:
        client = create_client()
        urls = []
        # /zhengce/ 页面可正常访问，zhengcewenjianku 有反爬
        list_pages = [
            f"{self.base_url}/zhengce/",
        ]
        for list_url in list_pages:
            try:
                resp = client.get(list_url)
                soup = BeautifulSoup(resp.text, "lxml")
                for a in soup.select("a[href]"):
                    href = a.get("href", "")
                    if "/zhengce/content/" in href:
                        full = href if href.startswith("http") else self.base_url + href
                        if full not in urls:
                            urls.append(full)
                        if len(urls) >= limit:
                            break
            except Exception:
                continue
            if len(urls) >= limit:
                break
        client.close()
        return urls[:limit]

    def parse_page(self, html: str, url: str) -> CrawledPage:
        import re
        soup = BeautifulSoup(html, "lxml")

        title = ""
        for sel in ["h1", ".article-title", ".pages-title", ".gov-title", "title"]:
            el = soup.select_one(sel)
            if el and el.get_text(strip=True):
                title = el.get_text(strip=True)
                break

        date_str = ""
        for sel in [".pages-date", ".article-date", ".info", ".date", ".pages-time", "meta[name=\"pubdate\"]",
                    "meta[name=\"publishdate\"]", "meta[name=\"dc.date\"]"]:
            el = soup.select_one(sel)
            if el:
                text = el.get("content", "") if sel.startswith("meta") else el.get_text(strip=True)
                m = re.search(r"(\d{4}[-/年]\d{1,2}[-/月]\d{1,2})", text)
                if m:
                    date_str = m.group(1)
                    break
        # Fallback: search page text for date pattern
        if not date_str:
            text = soup.get_text()[:3000]
            m = re.search(r"(\d{4}[-/年]\d{1,2}[-/月]\d{1,2})", text)
            if m:
                date_str = m.group(1)

        body_parts = []
        for sel in [".pages-content", "#UCAP-CONTENT", ".TRS_Editor",
                    ".article-content", ".con_text", "article"]:
            el = soup.select_one(sel)
            if el:
                for tag in el.select("script, style, nav, .banner, .footer"):
                    tag.decompose()
                text = el.get_text("\n", strip=True)
                if len(text) > 100:
                    body_parts.append(text)
                    break

        body_text = "\n\n".join(body_parts)
        if not body_text:
            paras = []
            for p in soup.select("p"):
                t = p.get_text(strip=True)
                if len(t) > 20:
                    paras.append(t)
            body_text = "\n\n".join(paras)

        return CrawledPage(url=url, title=title, body_text=body_text,
                           raw_html=html, published_date=date_str)


class CSRCAdapter:
    """证监会-法规监管"""
    name = "csrc"
    base_url = "https://www.csrc.gov.cn"

    def discover_urls(self, limit: int = 20) -> list[str]:
        import re
        client = create_client()
        urls = []
        # 多个列表页: 要闻、法规
        list_pages = [
            f"{self.base_url}/csrc/c100028/common_list.shtml",
            f"{self.base_url}/csrc/c100029/common_list.shtml",
        ]
        for list_url in list_pages:
            try:
                resp = client.get(list_url)
                soup = BeautifulSoup(resp.text, "lxml")
                for a in soup.select("a[href]"):
                    href = a.get("href", "")
                    # 匹配 /c100028/xxx/content.shtml 或 /c100029/xxx/content.shtml
                    if re.search(r"/c1000(28|29)/[a-z0-9]+/content\.shtml", href):
                        full = href if href.startswith("http") else self.base_url + href
                        if full not in urls:
                            urls.append(full)
                        if len(urls) >= limit:
                            break
            except Exception:
                continue
            if len(urls) >= limit:
                break
        client.close()
        return urls[:limit]

    def parse_page(self, html: str, url: str) -> CrawledPage:
        import re
        soup = BeautifulSoup(html, "lxml")

        # CSRC: 标题在 h2 中（h1 是"政府网站年度报表"）
        title = ""
        for sel in ["h2", ".detail-title", ".news-title"]:
            el = soup.select_one(sel)
            if el and el.get_text(strip=True) and len(el.get_text(strip=True)) > 5:
                title = el.get_text(strip=True)
                break

        # 日期: 在 .content div 的文本中查找
        date_str = ""
        for sel in [".content", ".article-content", ".detail-info"]:
            el = soup.select_one(sel)
            if el:
                m = re.search(r"(\d{4}[-/年]\d{1,2}[-/月]\d{1,2})", el.get_text(strip=True))
                if m:
                    date_str = m.group(1)
                    break

        # 正文: .detail-news 内容最干净, .content 包含元数据
        body_text = ""
        for sel in [".detail-news", ".content", ".article-content", ".TRS_Editor"]:
            el = soup.select_one(sel)
            if el:
                for tag in el.select("script, style, .share, .print"):
                    tag.decompose()
                text = el.get_text("\n", strip=True)
                if len(text) > 100:
                    body_text = text
                    break

        if not body_text:
            paras = [p.get_text(strip=True) for p in soup.select("p") if len(p.get_text(strip=True)) > 20]
            body_text = "\n\n".join(paras)

        return CrawledPage(url=url, title=title, body_text=body_text,
                           raw_html=html, published_date=date_str)


class BaiduBaikeAdapter:
    """百度百科-金融词条"""
    name = "baidu_baike"
    base_url = "https://baike.baidu.com"

    seed_items = [
        "货币政策", "财政政策", "金融市场", "证券投资", "银行监管",
        "金融风险管理", "资本市场", "保险业", "信托", "基金",
        "期货", "外汇", "利率", "汇率", "存款准备金",
        "金融科技", "数字货币", "绿色金融", "普惠金融", "金融衍生品",
    ]

    def discover_urls(self, limit: int = 20) -> list[str]:
        return [f"{self.base_url}/item/{item}" for item in self.seed_items[:limit]]

    def parse_page(self, html: str, url: str) -> CrawledPage:
        soup = BeautifulSoup(html, "lxml")

        title = ""
        el = soup.select_one("h1")
        if el:
            title = el.get_text(strip=True)

        body_parts = []
        # 百度百科使用 CSS Modules，class 名带 hash 后缀，用前缀匹配
        for el in soup.select('[class*="para_"]'):
            # 跳过包含 MODULE 标记的非内容元素
            classes = " ".join(el.get("class", []))
            text = el.get_text(strip=True)
            if len(text) > 10:
                body_parts.append(text)

        # 也尝试 lemma-summary 或 J-summary
        for el in soup.select('[class*="lemmaSummary"], [class*="J-summary"]'):
            text = el.get_text(strip=True)
            if len(text) > 10:
                body_parts.insert(0, text)

        body_text = "\n\n".join(body_parts)
        return CrawledPage(url=url, title=title, body_text=body_text, raw_html=html)


ADAPTERS: dict[str, SiteAdapter] = {
    "gov_zhengce": GovZhengceAdapter(),
    "csrc": CSRCAdapter(),
    "baidu_baike": BaiduBaikeAdapter(),
}
