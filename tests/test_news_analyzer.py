"""news_analyzer.py — STOCK_TOPIC_MAP 및 감성 집계 테스트"""

import config
import news_analyzer


def test_pltr_uses_stock_topic_map():
    """PLTR은 Palantir 전용 토픽으로 감성 점수를 받아야 함"""
    all_results = {
        "Palantir defense AI": {
            "score": 1,
            "label": "긍정",
            "keywords": ["defense", "AIP"],
            "reason": "Palantir 방산 AI 수주 확대",
        },
        "Nvidia AI chip": {
            "score": 2,
            "label": "매우긍정",
            "keywords": ["Blackwell"],
            "reason": "Nvidia 실적 호조",
        },
    }
    sent = news_analyzer.get_stock_sentiment("PLTR", all_results)
    assert sent["score"] == 1
    assert sent["label"] == "긍정"
    assert "Palantir" in sent["reason"] or sent["reason"]


def test_tsla_averages_multiple_topics():
    all_results = {
        "Elon Musk": {"score": 2, "label": "매우긍정", "keywords": [], "reason": "Musk 긍정"},
        "Tesla stock": {"score": 0, "label": "중립", "keywords": [], "reason": "Tesla 중립"},
    }
    sent = news_analyzer.get_stock_sentiment("TSLA", all_results)
    assert sent["score"] == 1  # (2+0)/2 = 1


def test_fallback_keyword_match_without_topic_map(monkeypatch):
    monkeypatch.setattr(config, "STOCK_TOPIC_MAP", {})
    all_results = {
        "Samsung Semiconductor": {
            "score": 2,
            "label": "매우긍정",
            "keywords": [],
            "reason": "삼성 반도체 호조",
        },
    }
    sent = news_analyzer.get_stock_sentiment("005930", all_results)
    assert sent["score"] == 2
