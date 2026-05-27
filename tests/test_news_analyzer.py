"""news_analyzer.py — STOCK_TOPIC_MAP 및 감성 집계 테스트"""

import config
import news_analyzer


def test_pltr_uses_stock_topic_map():
    """PLTR은 Palantir 전용 토픽으로 감성 점수를 받아야 함"""
    pltr_topic = config.STOCK_TOPIC_MAP["PLTR"][0]
    all_results = {
        pltr_topic: {
            "score": 1,
            "label": "긍정",
            "keywords": ["defense", "AIP"],
            "reason": "Palantir 방산 AI 수주 확대",
        },
        "Nvidia AI GPU data center chip": {
            "score": 2,
            "label": "매우긍정",
            "keywords": ["Blackwell"],
            "reason": "Nvidia 실적 호조",
        },
    }
    sent = news_analyzer.get_stock_sentiment("PLTR", all_results)
    assert sent["score"] == 1
    assert sent["label"] == "긍정"
    assert sent["reason"]


def test_tsla_single_topic():
    """TSLA는 단일 토픽으로 감성 점수를 받아야 함"""
    tsla_topic = config.STOCK_TOPIC_MAP["TSLA"][0]
    all_results = {
        tsla_topic: {"score": 2, "label": "매우긍정", "keywords": [], "reason": "Tesla 급등"},
    }
    sent = news_analyzer.get_stock_sentiment("TSLA", all_results)
    assert sent["score"] == 2


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


def test_parse_claude_json_strips_markdown_fence():
    raw = '```json\n{"score": 2, "label": "매우긍정", "keywords": ["a"], "reason": "ok"}\n```'
    parsed = news_analyzer._parse_claude_json(raw)
    assert parsed["score"] == 2
    assert parsed["label"] == "매우긍정"


def test_parse_claude_json_extracts_embedded_object():
    raw = 'Here is the result:\n{"score": 1, "label": "긍정", "keywords": [], "reason": "x"}'
    parsed = news_analyzer._parse_claude_json(raw)
    assert parsed["score"] == 1
