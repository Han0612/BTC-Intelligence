"""清理不可信外部文本。来源正文和链接绝不作为请求目标或执行内容。"""
import hashlib
import ipaddress
import re
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

FETCH_HOSTS = frozenset({
    "decrypt.co", "cointelegraph.com", "www.coindesk.com", "feeds.content.dowjones.io",
    "www.cnbc.com", "feeds.bloomberg.com", "www.federalreserve.gov", "www.sec.gov",
    "hn.algolia.com", "hacker-news.firebaseio.com",
})


def public_url(url: str) -> str:
    url = url.strip()
    if any(ord(c)<33 or ord(c)==127 for c in url):
        raise ValueError("外部 URL 含空白或控制字符")
    parts = urlsplit(url.strip())
    host = parts.hostname or ""
    if parts.scheme not in {"https", "http"} or not host or parts.username or parts.password:
        raise ValueError("外部链接必须为无凭据的 HTTP(S) URL")
    if parts.port not in {None, 443, 80} or "." not in host or host.endswith((".local", ".internal", ".localhost")):
        raise ValueError("拒绝本地或异常端口 URL")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError("拒绝 IP 字面量 URL")
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid"}]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", urlencode(query), ""))


def fetch_url(url: str) -> str:
    safe = public_url(url)
    parts = urlsplit(safe)
    if parts.scheme != "https" or parts.hostname not in FETCH_HOSTS or parts.port not in {None, 443}:
        raise ValueError("请求目标不在已审查的数据源 HTTPS 白名单中")
    return safe


class Cleaner(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "iframe", "object"}:
            self.hidden += 1
        elif tag in {"p", "br", "div", "li"}:
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "iframe", "object"}:
            self.hidden = max(0, self.hidden - 1)
        if tag in {"p", "div", "li"}:
            self.parts.append(" ")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def clean_text(value: str | None, limit: int = 12000) -> str:
    parser = Cleaner()
    parser.feed((value or "")[:100000])
    text = " ".join("".join(parser.parts).split())
    return re.sub(r"[\x00-\x1f\x7f\x1b]", "", text)[:limit]


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def language(text: str) -> str:
    if re.search(r"[\u4e00-\u9fff]", text):
        return "zh"
    return "en" if re.search(r"[a-zA-Z]", text) else "und"


def markdown_text(text: str) -> str:
    """报告中把外部文字作为纯文本，阻止其注入 Markdown 图像/链接。"""
    return re.sub(r"([\\`*{}\[\]()#+.!_>|~<])",r"\\\1",text)
