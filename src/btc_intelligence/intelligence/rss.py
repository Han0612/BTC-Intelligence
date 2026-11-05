"""仅解析明确配置的官方 RSS/Atom；不下载文章正文或嵌入资源。"""
import re
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit

from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException

from .safety import clean_text, digest, language, public_url
from .transport import FetchError


def timestamp(value, collected):
    if not value:
        return None,"MISSING"
    try:
        try:
            date = parsedate_to_datetime(value)
        except (ValueError,TypeError):
            date = datetime.fromisoformat(value.replace("Z","+00:00"))
        if date.tzinfo is None:
            return None,"MISSING_TIMEZONE"
        result = int(date.astimezone(UTC).timestamp()*1000)
        if result < 0 or result > collected+300000:
            return None,"INVALID_RANGE"
        return result,"SOURCE_PROVIDED"
    except (ValueError,TypeError,OverflowError):
        return None,"INVALID"


def local(tag):
    return tag.rsplit("}",1)[-1]


def parse_feed(body, source, collected):
    try:
        root = ET.fromstring(body)
    except (ET.ParseError,DefusedXmlException,ValueError) as exc:
        raise FetchError("RSS/Atom 格式异常："+type(exc).__name__) from None
    if local(root.tag) not in {"rss","RDF","feed"}:
        raise FetchError("响应不是 RSS/Atom")
    entries = [node for node in root.iter() if local(node.tag) in {"item","entry"}]
    articles, rejected = [], 0
    for entry in entries[:500]:
        fields = {}
        for child in entry:
            name = local(child.tag)
            if name == "link" and child.get("href") and child.get("rel","alternate") == "alternate":
                fields["link"] = child.get("href")
            elif name not in fields:
                fields[name] = "".join(child.itertext())
        try:
            url = public_url(fields.get("link", ""))
            title = clean_text(fields.get("title"),500)
            if not title:
                raise ValueError("空标题")
            # 官方源只标识其自己的公告，不能把外链的任何主张都当官方确认。
            if source.kind == "official" and urlsplit(url).hostname != urlsplit(source.url).hostname:
                raise ValueError("官方 feed 外链未核实")
        except ValueError:
            rejected += 1
            continue
        summary = clean_text(fields.get("description") or fields.get("summary"),1500)
        published_raw = (fields.get("pubDate") or fields.get("published") or fields.get("date") or "").strip()[:200]
        published,quality = timestamp(published_raw,collected)
        origin = source.id
        attribution = " ".join([fields.get("creator",""),fields.get("author",""),summary])
        match = re.search(r"(?:\bby\s+|\bsource:\s*|copyright\s*|©\s*|^)(Reuters|Associated Press|Bloomberg)\b",attribution,re.I)
        if match:
            origin = "wire:"+match.group(1).lower()
        articles.append({
            "external_id": clean_text(fields.get("guid") or fields.get("id") or url,2000),
            "title":title,"summary":summary,"body":None,"url":url,
            "language":language(title+summary),"published_at_ms":published,
            "published_raw":published_raw or None,"time_quality":quality,
            "collected_at_ms":collected,"content_hash":digest(title+"\n"+summary),"origin":origin,
        })
    if entries and not articles:
        raise FetchError("RSS 所有条目无效，未覆盖已有数据")
    return articles,rejected
