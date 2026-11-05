"""按要求核验既有报道的公开页面元数据；不请求订阅正文，不绕访问限制。"""
import asyncio
import json
from html.parser import HTMLParser
from urllib.parse import urlsplit,urljoin

import httpx

from ..models import now_ms
from .analysis import event_tokens
from .safety import public_url,clean_text

DOMAINS={'wsj':{'www.wsj.com','wsj.com'},'cnbc':{'www.cnbc.com','cnbc.com'},'decrypt':{'decrypt.co'},
         'cointelegraph':{'cointelegraph.com'},'fed':{'www.federalreserve.gov'},'sec':{'www.sec.gov'},
         'coindesk':{'www.coindesk.com','coindesk.com'},'bloomberg':{'www.bloomberg.com','bloomberg.com'}}


class Metadata(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.title='';self.in_title=False;self.meta={}
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='title':self.in_title=True
        if tag=='meta':self.meta[a.get('property') or a.get('name') or '']=a.get('content','')
    def handle_endtag(self,tag):
        if tag=='title':self.in_title=False
    def handle_data(self,data):
        if self.in_title:self.title+=data


def title_matches(expected,observed):
    a,b=event_tokens(expected),event_tokens(observed)
    return bool(a and b) and len(a&b)/min(len(a),len(b))>=0.8 and len(a&b)/max(len(a),len(b))>=0.6


async def audit_article(client,article):
    allowed=DOMAINS.get(article['source_id'],set());url=article['url']
    result={'article_id':article['id'],'checked_at_ms':now_ms(),'http_status':None,'url_domain_match':0,
            'page_title':None,'title_match':None,'page_published_raw':None,'access_status':'UNVERIFIABLE',
            'publisher_status':'UNVERIFIED','details':'','evidence_url':url}
    try:
        url=public_url(url)
        if urlsplit(url).scheme!='https' or urlsplit(url).hostname not in allowed:
            result['details']='原始 URL 不符合声明媒体的审查域名，未请求';return result
        result['url_domain_match']=1
        for _ in range(3):
            async with client.stream('GET',url,timeout=12,follow_redirects=False) as response:
                code=response.status_code;result['http_status']=code;result['evidence_url']=url
                if code in {401,403,429,451}:
                    result.update(access_status='RESTRICTED',details=f'HTTP {code}，无法独立核验；不判定真伪');return result
                if code in {301,302,307,308}:
                    target=public_url(urljoin(url,response.headers.get('location','')))
                    if urlsplit(target).scheme!='https' or urlsplit(target).hostname not in allowed:
                        result['details']='重定向超出同媒体已审查域名，未跟随';return result
                    url=target;continue
                if code!=200:
                    result.update(access_status='HTTP_ERROR',details=f'HTTP {code}，无法独立核验；链接失效不等于虚假');return result
                head=bytearray()
                async for chunk in response.aiter_bytes(chunk_size=16384):
                    head.extend(chunk)
                    if b'</head>' in head.lower() or len(head)>=700000:break
                parser=Metadata();parser.feed(head.decode('utf-8',errors='replace'))
                title=clean_text(parser.meta.get('og:title') or parser.meta.get('twitter:title') or parser.title,600)
                match=title_matches(article['title'],title)
                result.update(access_status='PUBLIC_METADATA',page_title=title,title_match=int(match),
                              page_published_raw=parser.meta.get('article:published_time') or parser.meta.get('date'),
                              publisher_status='PUBLISHER_PAGE_MATCH' if match else 'TITLE_NOT_VERIFIED',
                              details='仅证明该媒体页面标题对应；不证明报道事实或官方确认' if match else 'HTTP 200 但标题未对应/无充分元数据，需人工核验，未判定虚假')
                return result
        result['details']='重定向超过上限，无法核验'
    except (httpx.HTTPError,OSError,ValueError) as exc:
        result.update(access_status='NETWORK_ERROR',details=type(exc).__name__+'；无法独立核验，不判定虚假')
    return result


async def audit_sample(store,limit=24):
    selected=[];seen=set()
    for source in ('fed','sec','cnbc','wsj','decrypt','cointelegraph'):
        for row in store.db.execute('SELECT * FROM news_articles WHERE source_id=? ORDER BY published_at_ms DESC LIMIT 4',(source,)):
            selected.append(dict(row));seen.add(row['id'])
    for row in store.db.execute("SELECT * FROM news_articles WHERE category='GEOPOLITICS' OR title LIKE '%$6.3%' ORDER BY published_at_ms DESC LIMIT 6"):
        if row['id'] not in seen:selected.append(dict(row));seen.add(row['id'])
    selected=selected[:max(20,limit)]
    semaphore=asyncio.Semaphore(3)
    async with httpx.AsyncClient(trust_env=False,headers={'User-Agent':'BTCIntelligence/0.2 public-metadata-review'}) as client:
        async def one(article):
            async with semaphore:return await audit_article(client,article)
        results=await asyncio.gather(*(one(a) for a in selected))
    with store.db:
        for result in results:
            cols=list(result)
            store.db.execute('INSERT INTO article_validations('+','.join(cols)+') VALUES('+','.join('?' for _ in cols)+')',list(result.values()))
            if result['title_match'] and result['page_published_raw']:
                from .rss import timestamp
                published,quality=timestamp(result['page_published_raw'],result['checked_at_ms'])
                if published is not None:
                    store.db.execute('UPDATE news_articles SET verified_published_at_ms=?,verified_time_basis=? WHERE id=?',(published,'同媒体HTTP200页面公开 article:published_time，标题匹配；原RSS时间另存，非事件事实确认',result['article_id']))
    return [dict(result,title=article['title'],source_id=article['source_id'],original_url=article['url'],rss_published_ms=article['published_at_ms']) for result,article in zip(results,selected)]
