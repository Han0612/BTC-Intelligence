"""明确标注的人工测试集；不参与真实采集，不能当作代表性市场评测。"""
from .analysis import classify_comment, classify_news, RULE_VERSION

# 人工编写，非真实用户评论；含规则难以识别的同义表述，用来公开漏判。
CASES = [
 ("I am bullish on Bitcoin.","BULLISH"),
 ("I am buying more BTC.","BULLISH"),
 ("Bitcoin will rally.","BULLISH"),
 ("I am long BTC.","BULLISH"),
 ("BTC to the moon.","BULLISH"),
 ("我看多比特币。","BULLISH"),
 ("我正在做多 BTC。","BULLISH"),
 ("比特币将上涨。","BULLISH"),
 ("I expect Bitcoin to appreciate substantially.","BULLISH"),
 ("I am bearish on Bitcoin.","BEARISH"),
 ("I am shorting BTC.","BEARISH"),
 ("Bitcoin will crash.","BEARISH"),
 ("I am selling my Bitcoin.","BEARISH"),
 ("BTC 暴跌让我很开心，我一直在做空。","BEARISH"),
 ("我看空比特币。","BEARISH"),
 ("我卖出比特币。","BEARISH"),
 ("Bitcoin is headed for a collapse.","BEARISH"),
 ("I am neutral on Bitcoin.","NEUTRAL"),
 ("I have no position in BTC.","NEUTRAL"),
 ("Neither bullish nor bearish on Bitcoin.","NEUTRAL"),
 ("Bitcoin is range-bound.","NEUTRAL"),
 ("我对比特币保持中性。","NEUTRAL"),
 ("BTC 不多不空，继续观望。","NEUTRAL"),
 ("Bitcoin technology is great.","UNKNOWN"),
 ("I am not bullish on Bitcoin.","UNKNOWN"),
 ("I don't think Bitcoin will crash.","UNKNOWN"),
 ("BTC could rally if rates fall.","UNKNOWN"),
 ("Bitcoin to the moon, yeah right /s.","UNKNOWN"),
 ("有人说“看多比特币”，我不知道。","UNKNOWN"),
 ("不一定看空 BTC，也未必看多。","UNKNOWN"),
 ("Bitcoin and cryptographic signatures are interesting.","UNKNOWN"),
 ("I am bullish and bearish on BTC at the same time.","UNKNOWN"),
 ("Buy bitcoin? Maybe, if it falls.","UNKNOWN"),
 ("The weather is nice today.","UNKNOWN"),
 ("Bitcoin in the short term is difficult to value.","UNKNOWN"),
 ("I used to be bullish on BTC in 2017, now I have no view.","UNKNOWN"),
]

# 补充的人工质量样本，仍不是独立盲测或真实市场评论。
CASES += [
 ("I am bullish on Bitcoin technology, the protocol is elegant.","UNKNOWN"),
 ("I am bearish about Binance withdrawals.","UNKNOWN"),
 ("I am bullish on Ethereum, not Bitcoin.","UNKNOWN"),
 ("He is bullish on Bitcoin.","UNKNOWN"),
 ("朋友说看多 BTC，我只是在转述。","UNKNOWN"),
 ("I'm long BTC.","BULLISH"),
 ("I am short BTC.","BEARISH"),
 ("I am not short BTC.","UNKNOWN"),
 ("If Bitcoin falls I might buy.","UNKNOWN"),
 ("I worry about exchange security after the Bitcoin story.","UNKNOWN"),
 ("BTC is sideways, I am neutral.","NEUTRAL"),
 ("我观望比特币，不多不空。","NEUTRAL"),
]

NEWS_CASES = [
 ("US-Iran military conflict escalates", "INDIRECT", "GEOPOLITICS"),
 ("Federal Reserve issues FOMC interest rate decision", "INDIRECT", "MONETARY_POLICY"),
 ("US CPI inflation data surprise markets", "INDIRECT", "ECONOMIC_DATA"),
 ("Bank run sparks systemic crisis", "INDIRECT", "FINANCIAL_RISK"),
 ("Oil supply shock hits energy prices", "INDIRECT", "ENERGY"),
 ("New tariffs raise trade war fears", "INDIRECT", "TRADE_POLICY"),
 ("Bitcoin ETF receives new inflows", "DIRECT", "ETF"),
 ("Binance exchange halts withdrawals", "DIRECT", "EXCHANGE"),
 ("Local garden wins flower competition", "IRRELEVANT", "OTHER"),
]


def evaluate():
    labels=["BULLISH","BEARISH","NEUTRAL","UNKNOWN"]
    matrix={expected:{predicted:0 for predicted in labels} for expected in labels}
    errors=[]
    for text,expected in CASES:
        result=classify_comment(text,"Bitcoin price outlook")
        matrix[expected][result.label]+=1
        if result.label!=expected:
            errors.append({"text":text,"expected":expected,"predicted":result.label,"reason":result.reason})
    news_errors=[]
    for title,relevance,category in NEWS_CASES:
        result=classify_news(title)
        if (result.relevance,result.category)!=(relevance,category):
            news_errors.append({"title":title,"expected":[relevance,category],"predicted":[result.relevance,result.category]})
    return {"version":RULE_VERSION,"dataset":"人工合成自测集，非真实评论、非独立盲测，不代表泛化准确率",
            "comment_samples":len(CASES),"comment_correct":len(CASES)-len(errors),"accuracy":round((len(CASES)-len(errors))/len(CASES),4),
            "confusion_matrix_rows_expected_columns_predicted":matrix,"comment_errors":errors,
            "per_class":{label:{"precision":round(matrix[label][label]/sum(matrix[truth][label] for truth in labels),4) if sum(matrix[truth][label] for truth in labels) else None,"recall":round(matrix[label][label]/sum(matrix[label].values()),4) if sum(matrix[label].values()) else None,"support":sum(matrix[label].values())} for label in labels},
            "news_samples":len(NEWS_CASES),"news_correct":len(NEWS_CASES)-len(news_errors),"news_errors":news_errors}
