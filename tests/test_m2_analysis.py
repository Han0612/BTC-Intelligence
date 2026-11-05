import pytest

from btc_intelligence.intelligence.analysis import classify_comment,classify_news,comment_relevance,same_event
from btc_intelligence.intelligence.evaluation import evaluate


@pytest.mark.parametrize("title,category",[("US-Iran military conflict escalates","GEOPOLITICS"),("Federal Reserve raises interest rates","MONETARY_POLICY"),("Bank run sparks systemic crisis","FINANCIAL_RISK"),("Oil supply disruption","ENERGY"),("US imposes tariffs in trade war","TRADE_POLICY")])
def test_macro_without_bitcoin_is_indirect_with_hypothetical_path(title,category):
    result=classify_news(title)
    assert result.relevance=="INDIRECT" and result.category==category and result.paths
    assert result.verification=="MEDIA_REPORT"


def test_direct_irrelevant_rumor_and_official_are_distinct():
    assert classify_news("Bitcoin ETF approval").relevance=="DIRECT"
    assert classify_news("Local flowers win garden competition").relevance=="IRRELEVANT"
    assert classify_news("Unconfirmed military conflict escalates").verification=="UNVERIFIED"
    assert classify_news("Federal Reserve FOMC statement",official=True).verification=="OFFICIAL_STATEMENT"
    assert classify_news("US-Iran military conflict escalates").importance=="Critical"
    assert classify_news("Opinion | Military conflict and oil").verification=="OPINION"


@pytest.mark.parametrize("text,label",[("BTC 暴跌让我很开心，我一直在做空。","BEARISH"),("Bitcoin technology is great.","UNKNOWN"),("I am bullish on Bitcoin.","BULLISH"),("Not bullish on BTC.","UNKNOWN"),("Bitcoin to the moon /s.","UNKNOWN"),("I am neutral on BTC.","NEUTRAL"),("If BTC goes up I might buy.","UNKNOWN"),("Bitcoin in the short term is difficult to value.","UNKNOWN"),("I used to be bullish on BTC in 2017, now I have no view.","UNKNOWN")])
def test_comment_direction_is_not_generic_positive_or_negative(text,label):
    assert classify_comment(text).label==label


def test_relevance_excludes_technology_only_comments():
    assert comment_relevance("Cryptographic signatures are great","Bitcoin technology")=="IRRELEVANT"
    assert comment_relevance("I am buying BTC","Bitcoin market")=="RELEVANT"
    assert comment_relevance("The prize money and value of this exploit are low","Show HN: Steal My Bitcoin")=="IRRELEVANT"


def test_specific_incident_aggregation_and_false_positive_guards():
    assert same_event("Binance says withdrawals open after $6.3B hack","Binance resumes withdrawals after $6.3 billion hack","EXCHANGE")
    assert not same_event("Binance $6.3B hack","Coinbase $6.3B hack","EXCHANGE")
    assert not same_event("Binance $6.3B hack","Binance $2B hack","EXCHANGE")
    assert classify_news("Best High-Yield Savings Accounts of October","Compare interest rates").relevance=="IRRELEVANT"
    assert classify_news("Court dismisses lawsuit against Wall Street Journal").relevance=="IRRELEVANT"


def test_evaluation_has_all_four_labels_and_discloses_errors():
    result=evaluate()
    matrix=result["confusion_matrix_rows_expected_columns_predicted"]
    assert sum(sum(row.values()) for row in matrix.values())==result["comment_samples"]
    assert result["comment_samples"]>=30 and result["news_correct"]==result["news_samples"]
    assert "合成" in result["dataset"] and result["comment_errors"]
