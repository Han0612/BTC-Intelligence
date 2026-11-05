"""透明规则 v1：新闻优先级不代表价格预测；只识别评论中的明确方向观点。"""
import re
from dataclasses import asdict, dataclass

RULE_VERSION = "m2-quality-2.0"
BTC = r"\b(?:bitcoin|btc|xbt)\b|比特币"
CRYPTO = BTC + r"|\b(?:crypto|binance|ethereum|stablecoin|tether|usdt|coinbase)\b|加密货币|稳定币|币安"

# 顺序是可解释的监控优先级，不是涨跌判断。
TOPICS = [
    ("GEOPOLITICS", r"\b(?:wars?|military|missiles?|invasions?|ceasefires?|airstrikes?|sanctions|drones?|negotiations|conflicts?)\b|战争|军事|导弹|冲突升级|制裁|停火|安全危机", "High", "能源供应、通胀预期、美元与避险需求、全球风险偏好可能改变；对 BTC 的方向尚待市场验证。"),
    ("MONETARY_POLICY", r"\b(?:fomc|federal reserve|fed|interest rates?|rate cuts?|rate hikes?|central bank|ecb|boj|monetary)\b|美联储|央行|降息|加息|利率决议", "High", "政策利率及流动性预期可能影响美债收益率、美元和风险资产估值，进而影响 BTC。"),
    ("ECONOMIC_DATA", r"\b(?:cpi|pce|nonfarm|payrolls|gdp|inflation|unemployment|jobs report)\b|通胀|非农|就业数据|国内生产总值", "High", "经济数据可能改变通胀、增长与利率预期，再经美元和风险偏好传导至 BTC。"),
    ("FINANCIAL_RISK", r"\b(?:bank run|banking crisis|bank failure|systemic|liquidity crisis|treasury yields?|bond yields?|dollar index|stock market|s&p 500|nasdaq)\b|银行危机|挤兑|流动性危机|美债|美元指数|美股", "High", "融资条件、美元与金融体系风险可能改变风险资产流动性和 BTC 风险偏好。"),
    ("TRADE_POLICY", r"\b(?:tariffs?|trade war|trade deal|fiscal|government shutdown)\b|关税|贸易战|财政|政府停摆", "High", "贸易与财政政策可能影响增长、通胀、融资条件及风险偏好。"),
    ("ENERGY", r"\b(?:oil|natural gas|energy supply|opec|strait of hormuz)\b|原油|天然气|能源供应|霍尔木兹", "High", "能源价格与供应可能改变通胀和政策预期，经利率、美元与风险偏好影响 BTC。"),
    ("ETF", r"\betfs?\b|交易所交易基金", "High", "ETF 审批与资金变动可能影响加密资产需求；标题不能替代真实净流量数据。"),
    ("EXCHANGE", r"\b(?:binance|coinbase|exchange|withdrawals?|insolven|bankrupt)\b|交易所|币安|暂停提现|破产", "Medium", "交易所运营与偿付风险可能影响加密市场流动性和信任。"),
    ("CRYPTO_SECURITY", r"\b(?:hack|hacked|heist|exploit|stolen)\b|黑客|被盗|漏洞利用", "High", "安全事件可能引发资产损失、流动性变化及风险偏好调整。"),
    ("REGULATION", r"\b(?:sec|regulat|enforcement|securities|legislation)\w*\b|监管|证监会|立法", "Medium", "监管变化可能影响市场准入、资本流向和合规成本。"),
    ("INSTITUTIONAL", r"\b(?:treasury|institutional|strategy|microstrategy|holdings|acquisition)\b|机构|增持|持仓|购买计划", "Medium", "机构资产配置可能影响供需；需核验披露与实际规模。"),
    ("ONCHAIN", r"\b(?:mining|miner|hashrate|halving|on.chain)\b|矿工|算力|减半|链上", "Medium", "链上活动和供给变化可能影响市场预期，需结合量化数据核验。"),
]


@dataclass(frozen=True)
class NewsAnalysis:
    category: str
    relevance: str
    importance: str
    verification: str
    assets: list[str]
    paths: list[str]
    evidence: list[str]
    version: str = RULE_VERSION
    content_type: str = "UNRELATED"

    def record(self):
        return asdict(self)


def classify_news(title: str, summary: str = "", official: bool = False) -> NewsAnalysis:
    text = (title + " " + summary).lower()
    head = title.lower()
    direct = bool(re.search(CRYPTO, head, re.I))
    category, importance, paths, evidence = "OTHER", "Low", [], []
    content_type = "UNRELATED"
    consumer = re.search(r"best .*(?:savings accounts|credit cards|mortgages)|购物推荐|信用卡推荐",head)
    # 强事件信号优先于普通关键词；只在主标题不足时使用摘要补充同一主张。
    geo = re.sub(r"\btrade war\b", "trade_conflict", head)
    gates = [
        ("GEOPOLITICS", r"\b(?:war|military conflict|invasion|airstrikes?|missile attacks?|ceasefire|sanctions)\b|战争|军事冲突|空袭|导弹袭击|制裁|停火", geo),
        ("GEOPOLITICS", r"(?:iran|israel|russia|ukraine|gulf|hormuz).*(?:conflict|military|negotiations|strikes|attack)|(?:conflict|military|negotiations|strikes|attack).*(?:iran|israel|russia|ukraine|gulf|hormuz)|美伊.*谈判|冲突升级", geo),
        ("MONETARY_POLICY", r"\b(?:fomc|federal reserve|fed|central bank|ecb|boj|bank of japan)\b.*(?:statement|rate|policy|decision|speech|liquidity|cut|hike)|美联储|央行.*(?:政策|利率|降息|加息)|利率决议", head),
        ("ECONOMIC_DATA", r"\b(?:cpi|pce|nonfarm|payrolls|gdp|jobs report)\b|(?:us|u\.s\.).*(?:inflation|unemployment).*(?:data|report|surprise|rise|fall)|非农|美国.*(?:通胀|就业数据)|国内生产总值", head),
        ("FINANCIAL_RISK", r"bank run|banking crisis|bank failure|systemic crisis|liquidity crisis|treasury yields?|bond yields?|dollar index|treasury clearing|银行危机|挤兑|流动性危机|美债收益率|美元指数", head),
        ("FINANCIAL_RISK", r"(?:stock market|s&p 500|nasdaq|美股).*(?:plung|crash|selloff|rally|surge|drop|record|暴跌|大涨)|(?:plung|crash|selloff|rally).*(?:stock market|s&p 500|nasdaq)",head),
        ("TRADE_POLICY", r"tariffs?|trade war|government shutdown|(?:fiscal|budget).*(?:stimulus|trillion|crisis|shock)|关税|贸易战|政府停摆|财政刺激",head),
        ("ENERGY", r"(?:oil|natural gas|energy|gasoline).*(?:supply|shock|disrupt|price|cost|surge|soar)|(?:supply|shock|disrupt).*(?:oil|natural gas)|原油.*(?:价格|供应)|能源供应", head),
    ]
    if not consumer:
        for topic, pattern, section in gates:
            match=re.search(pattern,section,re.I)
            if match:
                category=topic;importance="High";evidence=[match.group(0)]
                paths=[next(item[3] for item in TOPICS if item[0]==topic)]
                content_type="MAJOR_GEOPOLITICAL" if topic=="GEOPOLITICS" else "MAJOR_MACRO_FINANCIAL"
                break
    if direct and not consumer:
        content_type="CRYPTO_DIRECT"
        category,importance,paths,evidence="CRYPTO","Medium",[],[re.search(CRYPTO,head,re.I).group(0)]
        for topic,pattern,level,path in TOPICS[6:]:
            match=re.search(pattern,head,re.I)
            if match:
                category,importance,paths,evidence=topic,level,[path],[match.group(0)];break
        if re.search(r"hack|heist|exploit|breach|stolen|halt.*withdraw|暂停提现|被盗|outflows",head):
            importance="High"
        if re.search(r"\betfs?\b",head) and re.search(BTC,head,re.I):
            category,importance="ETF","High"
            paths=[next(item[3] for item in TOPICS if item[0]=="ETF")]
    relevance="DIRECT" if content_type=="CRYPTO_DIRECT" else ("INDIRECT" if content_type.startswith("MAJOR_") else "IRRELEVANT")
    if re.search(r"military conflict escalat\w*|outbreak of war|declares? war|systemic crisis|bank run|战争爆发|冲突升级|系统性金融危机|挤兑",head) and relevance=="INDIRECT":
        importance="Critical"
    if re.search(r"(?:unexpected|emergency|surprise).*(?:rate|fomc)|意外.*利率决议",head) and category=="MONETARY_POLICY":
        importance="Critical"
    if relevance=="IRRELEVANT":
        paths=[]
        if re.search(r"senate|election|social security|retirement|benefits|business|company|corporate|earnings|\bai\b|strategy|银行|退休|选举|福利|企业",head):
            content_type="ORDINARY_FINANCE_POLITICS"
        if len(title.strip())<8 or re.search(r"^something big|^major news|重大消息待公布|^breaking$",head):
            relevance="UNKNOWN";content_type="INSUFFICIENT"
    rumor = re.search(r"\b(?:rumou?rs?|unconfirmed|alleged|reportedly|sources? says?)\b|传闻|网传|未经证实|据传",text)
    opinion = re.search(r"^opinion\s*[|:]|^评论[：:｜]|^观点[：:｜]",title,re.I)
    verification="UNVERIFIED" if rumor else ("OFFICIAL_STATEMENT" if official else ("OPINION" if opinion else "MEDIA_REPORT"))
    assets=[asset for asset,pattern in [("BTC",BTC),("CRYPTO",CRYPTO),("USD",r"\bdollar\b|美元"),("OIL",r"\boil\b|原油"),("US_EQUITIES",r"s&p 500|nasdaq|美股")] if re.search(pattern,text,re.I)]
    return NewsAnalysis(category,relevance,importance,verification,assets,paths,evidence,content_type=content_type)


FINANCE = r"\b(?:price|market|buy|buying|bought|sell|selling|sold|bullish|bearish|shorting|invest\w*|profit|loss|money|currency|dollar|valuation|worth|value|trade|trading|hold|holding|crash|rally|portfolio|speculat\w*)\b|价格|看多|看空|做多|做空|买入|卖出|上涨|下跌|暴跌|投资|交易|持有|货币|赚钱|亏损"


def comment_relevance(text: str, thread_title: str) -> str:
    if technical_thread(thread_title):
        return "IRRELEVANT"
    if re.search(BTC, text + " " + thread_title, re.I) and re.search(FINANCE, text, re.I):
        return "RELEVANT"
    return "IRRELEVANT"


def technical_thread(title: str) -> bool:
    return bool(re.search(r"\bctf\b|steal my bitcoin|heatbit|water heater|bitcoin puzzle|cryptographic|tcp out.of.memory",title,re.I))


@dataclass(frozen=True)
class Sentiment:
    label: str
    strength: float
    reason: str
    version: str = RULE_VERSION


def classify_comment(text: str, thread_title: str = "") -> Sentiment:
    text = text.lower().strip()
    if not re.search(BTC, text + " " + thread_title, re.I):
        return Sentiment("UNKNOWN", 0, "缺少 BTC 语境")
    if re.search(r'(?:bullish|bearish|long|short).{0,25}(?:gold|ethereum|\beth\b|solana|binance|exchange|crypto industry)|(?:看多|看空).{0,8}(?:黄金|以太坊|交易所)',text) and not re.search(r'(?:bullish|bearish|long|short).{0,15}(?:bitcoin|\bbtc\b)|(?:看多|看空|做多|做空).{0,8}(?:比特币|btc)',text):
        return Sentiment('UNKNOWN',0,'观点对象是其他资产/行业/交易所，不能移作 BTC 价格方向')
    if re.search(r'technology|cryptograph|protocol|技术|密码学',text) and not re.search(r'price|buy|selling|shorting|will (?:rise|fall)|价格|做多|做空|买入|卖出',text):
        return Sentiment('UNKNOWN',0,'比特币技术态度不是价格或持仓观点')
    if re.search(r"/s\b|yeah right|sarcas|讽刺|呵呵|笑死|[\"“”]", text):
        return Sentiment("UNKNOWN", 0, "反讽、转述或引语存在歧义")
    if re.search(r'\b(?:he|she|they|analysts?|someone) (?:is|are|said|says|expects?).*(?:bullish|bearish|bitcoin|btc)|他说|她说|有人说|朋友说|分析师称',text):
        return Sentiment('UNKNOWN',0,'转述他人观点，不能视为评论者自己的 BTC 方向立场')
    if re.search(r"\b(?:used to|was bullish|was bearish|no view)\b|过去看多|过去看空|以前看多|以前看空", text):
        return Sentiment("UNKNOWN", 0, "历史立场不能代替当前观点")
    if re.search(r"\bnot neutral\b|不是中性|[?？]",text):
        return Sentiment("UNKNOWN",0,"否定中性或疑问表达，缺少可靠方向")
    if re.search(r"\b(?:neutral|no position|neither bullish nor bearish|range.bound|sideways)\b|中性|不多不空|震荡|观望", text):
        return Sentiment("NEUTRAL", 0.7, "明确中性或观望观点")
    if re.search(r"\b(?:not|never|isn't|isn’t|don't|don’t|doesn't|can't|cannot|won't|wouldn't)\b|不看多|不看空|不买|不卖|不会|未必|不一定", text):
        return Sentiment("UNKNOWN", 0, "否定或复杂语境，规则无法可靠判断")
    if re.search(r"\b(?:if|might|could|maybe|perhaps|would)\b|如果|可能|也许|假如|据说", text):
        return Sentiment("UNKNOWN", 0, "条件、推测或转述，缺少明确自身立场")
    bullish = re.search(r"\b(?:bullish|buy(?:ing)?(?: more)? (?:btc|bitcoin)|long (?:btc|bitcoin)|(?:btc|bitcoin) (?:will|is going to) (?:rise|rally|moon|surge)|(?:btc|bitcoin) to the moon)\b|看多|做多|买入比特币|买入btc|比特币将上涨|btc将上涨", text, re.I)
    bearish = re.search(r"\b(?:bearish|short(?:ing)? (?:btc|bitcoin|it)|sell(?:ing)?(?: my)? (?:btc|bitcoin)|(?:btc|bitcoin) (?:will|is going to) (?:fall|crash|drop))\b|看空|做空|卖出比特币|卖出btc|比特币将下跌|btc将下跌", text, re.I)
    if bullish and bearish:
        return Sentiment("UNKNOWN", 0, "方向冲突，可能是比较或对冲")
    if bullish:
        return Sentiment("BULLISH", 0.8, "明确看多表述：" + bullish.group(0))
    if bearish:
        return Sentiment("BEARISH", 0.8, "明确看空表述：" + bearish.group(0))
    return Sentiment("UNKNOWN", 0, "缺少明确 BTC 价格或持仓方向；技术赞美不等于看多")


def event_tokens(title: str) -> set[str]:
    stop = {"the", "a", "an", "of", "to", "in", "on", "as", "and", "for", "is", "with", "says", "after", "new", "its", "from", "by"}
    return {t for t in re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]{2,}", title.lower()) if t not in stop and len(t) > 1}


def same_event(title: str, other: str, category: str) -> bool:
    a, b = event_tokens(title), event_tokens(other)
    if not a or not b:
        return False
    if a == b:
        return True
    for entities in ({'binance','coinbase','kraken'}, {'fed','ecb','boj'}, {'iran','israel','russia','ukraine'}):
        left,right=a&entities,b&entities
        if left and right and not left&right:
            return False
    dates=lambda value:set(re.findall(r'\b20\d{2}-\d{2}-\d{2}\b',value))
    if dates(title) and dates(other) and not dates(title)&dates(other):
        return False
    if category in {"EXCHANGE","CRYPTO_SECURITY"}:
        # 安全事件须同时具备相同交易所、事故词及相同明确金额，避免按品牌笼统合并。
        incident=r"\b(?:hack|hacked|heist|stolen)\b"
        for actor in ("binance","coinbase"):
            if actor in a & b and re.search(incident,title,re.I) and re.search(incident,other,re.I):
                amount=lambda value:set(re.findall(r"\b(\d+(?:\.\d+)?)\s*(?:billion|bn|b\b)",value.lower()))
                if amount(title) & amount(other):
                    return True
                if amount(title) and amount(other):
                    return False
    # 不仅按宏观主题合并；保守要求标题具有具体共同信息。
    return category != "OTHER" and len(a & b) >= 3 and len(a & b) / len(a | b) >= 0.55
