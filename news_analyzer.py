"""
news_analyzer.py — 뉴스 수집 + Claude 감성 분석 모듈

[동작 방식]
1. feedparser로 Google News RSS 파싱 (무료, API 키 불필요)
2. 수집된 헤드라인을 Claude에게 전달 → 감성 점수 반환
3. 1시간 캐시로 중복 API 호출 방지 (비용 최적화)

[감성 점수 스펙]
  +2: 매우 긍정 (강한 매수 시그널)
  +1: 긍정
   0: 중립
  -1: 부정
  -2: 매우 부정 (매수 금지)
"""

import hashlib
import json
import re
import time
import random
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo
import config

KST = ZoneInfo("Asia/Seoul")

# ──────────────────────────────────────────────
# 캐시 저장소 (메모리 내 1시간 TTL)
# ──────────────────────────────────────────────
_cache: dict[str, dict] = {}          # topic → {result, expires_at}
_seen_hashes: set[str] = set()        # 중복 뉴스 해시 필터


def _hash_headlines(headlines: list[str]) -> str:
    joined = "|".join(sorted(headlines[:10]))
    return hashlib.md5(joined.encode()).hexdigest()


# ──────────────────────────────────────────────
# Google News RSS 수집
# ──────────────────────────────────────────────

def fetch_news_headlines(topic: str, max_items: int = 5) -> list[str]:
    """Google News RSS에서 헤드라인 수집 (feedparser 사용)"""
    try:
        import feedparser
        encoded = topic.replace(" ", "+")
        url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
        feed = feedparser.parse(url)
        headlines = []
        for entry in feed.entries[:max_items]:
            title = entry.get("title", "").strip()
            if title:
                headlines.append(title)
        return headlines
    except ImportError:
        print("[WARN] feedparser 미설치. pip install feedparser 실행 필요.")
        return []
    except Exception as e:
        print(f"[WARN] 뉴스 수집 실패 ({topic}): {e}")
        return []


# ──────────────────────────────────────────────
# Mock 뉴스 데이터 (API 없을 때 사용)
# ──────────────────────────────────────────────

_MOCK_NEWS_POOL = {
    "Elon Musk": [
        "Elon Musk announces major SpaceX milestone, stock market reacts positively",
        "Tesla unveils next-gen FSD v13 – analysts upgrade price targets",
        "Musk meets with key tech leaders, discusses AI infrastructure investment",
        "SpaceX Starship completes successful orbital test flight",
        "Elon Musk's X platform signs major partnership boosting revenue",
    ],
    "SpaceX": [
        "SpaceX secures $2B NASA contract for lunar mission",
        "Starlink expands to 80 countries, subscriber base hits 5M",
        "SpaceX Starship launch window confirmed – major aerospace stocks rally",
        "South Korean satellite launched via SpaceX Falcon 9",
        "SpaceX partners with Samsung for advanced satellite chips",
    ],
    "Samsung Semiconductor": [
        "Samsung wins record $10B DRAM order from major hyperscaler",
        "Samsung 3nm HBM4 chip outperforms SK Hynix in benchmark tests",
        "Samsung Electronics Q2 profit beats consensus by 30%",
        "Samsung Semiconductor expands Texas fab amid AI chip demand surge",
        "Global memory market recovery accelerates – Samsung main beneficiary",
    ],
    "SK Hynix HBM": [
        "SK Hynix HBM3E selected exclusively for Nvidia H200 GPU",
        "HBM demand to triple in 2025 – SK Hynix raises guidance",
        "SK Hynix invests $3.87B in US fab for AI memory chips",
        "SK Hynix beats Q1 estimates, raises annual outlook on HBM boom",
        "Analysts raise SK Hynix price target citing AI demand boom",
    ],
    "HMG AI Hyundai": [
        "Hyundai Motor unveils AI-powered autonomous vehicle platform",
        "Hyundai-Boston Dynamics robot goes into mass production",
        "Hyundai Motor Group posts record-high operating profit on EV growth",
        "HMG AI software division secures major US defense contract",
        "Hyundai EVs gain top safety ratings, boosting stock outlook",
    ],
    "Tesla stock": [
        "Tesla Q2 deliveries beat estimates by 15%, shares surge 8%",
        "Tesla Cybertruck production ramps up, margin improving",
        "Tesla FSD v13 achieves Level 4 autonomy in California",
        "Morgan Stanley raises Tesla target to $400 on robotaxi potential",
        "Tesla energy storage business hits record quarterly deployment",
    ],
    "Nvidia AI chip": [
        "Nvidia Blackwell GPU orders surge, backlog extends to 2026",
        "Nvidia reports 122% revenue growth, smashes estimates",
        "Nvidia partners with Samsung for next-gen AI memory integration",
        "AI infrastructure spending boom accelerates Nvidia growth",
        "Nvidia CEO Jensen Huang hints at next-gen chip at GTC",
    ],
    "Palantir defense AI": [
        "Palantir wins $480M US Army AI contract extension",
        "Palantir AIP platform adoption accelerates among defense contractors",
        "Palantir beats Q2 revenue estimates on government AI demand",
        "Defense AI spending bill boosts Palantir and peers",
        "Palantir partners with NATO allies on battlefield analytics",
    ],
}

_MOCK_SCORES = {
    "Elon Musk":          2,
    "SpaceX":             2,
    "Samsung Semiconductor": 1,
    "SK Hynix HBM":       2,
    "HMG AI Hyundai":     1,
    "Tesla stock":        2,
    "Nvidia AI chip":     2,
    "Palantir defense AI": 1,
}


def _mock_sentiment(topic: str, headlines: list[str]) -> dict:
    """Mock: Claude 없이 가짜 감성 점수 생성"""
    base_score = _MOCK_SCORES.get(topic, 0)
    # ±1 노이즈 추가
    score = max(-2, min(2, base_score + random.choice([-1, 0, 0, 1])))
    label_map = {2: "매우긍정", 1: "긍정", 0: "중립", -1: "부정", -2: "매우부정"}
    kw = topic.split()[:3]
    return {
        "score": score,
        "label": label_map[score],
        "keywords": kw,
        "reason": f"[MOCK] '{topic}' 관련 긍정 뉴스 {len(headlines)}건 감지. "
                  f"핵심 내용: {headlines[0][:80] if headlines else '없음'}",
        "headlines_used": len(headlines),
    }


# ──────────────────────────────────────────────
# Claude API 감성 분석
# ──────────────────────────────────────────────

def _extract_message_text(message: object) -> str:
    parts: list[str] = []
    for block in getattr(message, "content", []) or []:
        if getattr(block, "type", None) == "text":
            text = getattr(block, "text", "")
            if text:
                parts.append(str(text))
    return "\n".join(parts).strip()


def _parse_claude_json(raw: str) -> dict | list:
    text = raw.strip()
    if not text:
        raise json.JSONDecodeError("empty Claude response", text, 0)

    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        for pattern in (r"\{[\s\S]*\}", r"\[[\s\S]*\]"):
            match = re.search(pattern, text)
            if match:
                return json.loads(match.group())
        raise


def _claude_sentiment(topic: str, headlines: list[str]) -> dict:
    """Claude API로 뉴스 감성 분석"""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

        headlines_text = "\n".join(f"- {h}" for h in headlines)
        prompt = f"""You are a financial sentiment analyst. Analyze these news headlines about "{topic}" for stock market impact.

Headlines:
{headlines_text}

Respond ONLY with valid JSON (no markdown, no explanation):
{{
  "score": <integer: -2=very_negative, -1=negative, 0=neutral, 1=positive, 2=very_positive>,
  "label": <"매우부정"|"부정"|"중립"|"긍정"|"매우긍정">,
  "keywords": [<top 3-5 key terms from headlines>],
  "reason": <one concise Korean sentence explaining the score>
}}"""

        message = client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = _extract_message_text(message)
        result = _parse_claude_json(raw)
        if not isinstance(result, dict):
            raise ValueError("Claude response was not a JSON object")
        result["headlines_used"] = len(headlines)
        return result

    except json.JSONDecodeError as e:
        preview = raw[:120].replace("\n", " ") if "raw" in locals() and raw else ""
        print(f"[WARN] Claude 응답 파싱 실패: {e} preview={preview!r}")
        return {"score": 0, "label": "중립", "keywords": [], "reason": "분석 실패", "headlines_used": 0}
    except Exception as e:
        print(f"[WARN] Claude API 오류: {e} → 중립 처리")
        return {"score": 0, "label": "중립", "keywords": [], "reason": f"API 오류: {e}", "headlines_used": 0}


# ──────────────────────────────────────────────
# 메인 진입점
# ──────────────────────────────────────────────

def analyze_topic(topic: str, force_refresh: bool = False) -> dict:
    """
    주어진 토픽의 뉴스를 수집하고 감성 분석을 수행.
    결과를 1시간 캐시하여 API 비용 절감.

    Returns:
        {
          "score": int,        # -2 ~ +2
          "label": str,
          "keywords": list,
          "reason": str,
          "headlines": list,
          "cached": bool,
          "analyzed_at": str,
        }
    """
    now = datetime.now(KST)

    # 캐시 확인
    if not force_refresh and topic in _cache:
        cached = _cache[topic]
        if now < cached["expires_at"]:
            result = cached["result"].copy()
            result["cached"] = True
            return result

    # 뉴스 수집
    if config.MOCK_MODE:
        headlines = _MOCK_NEWS_POOL.get(topic, [f"[MOCK] News about {topic}"])
    else:
        headlines = fetch_news_headlines(topic, max_items=config.NEWS_MAX_PER_TOPIC)

    if not headlines:
        return {
            "score": 0, "label": "중립", "keywords": [],
            "reason": "수집된 뉴스 없음", "headlines": [],
            "cached": False, "analyzed_at": now.strftime("%H:%M"),
        }

    # 중복 해시 체크
    h_hash = _hash_headlines(headlines)
    if h_hash in _seen_hashes and not force_refresh:
        # 동일 뉴스셋 → 이전 캐시 반환
        if topic in _cache:
            result = _cache[topic]["result"].copy()
            result["cached"] = True
            return result
    _seen_hashes.add(h_hash)

    # 감성 분석
    if config.MOCK_MODE or "여기에" in config.ANTHROPIC_API_KEY:
        sentiment = _mock_sentiment(topic, headlines)
    else:
        sentiment = _claude_sentiment(topic, headlines)

    result = {
        **sentiment,
        "headlines": headlines,
        "cached": False,
        "analyzed_at": now.strftime("%H:%M"),
        "topic": topic,
    }

    # 캐시 저장 (1시간 TTL)
    _cache[topic] = {
        "result": result,
        "expires_at": now + timedelta(minutes=config.NEWS_FETCH_INTERVAL_MIN),
    }
    return result


def _claude_sentiment_batch(topic_headlines: dict[str, list[str]]) -> dict[str, dict]:
    """여러 토픽을 단일 Claude 호출로 일괄 분석 (API 비용 절감)"""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

        blocks = []
        for topic, headlines in topic_headlines.items():
            hl = "\n".join(f"  - {h}" for h in headlines[: config.NEWS_MAX_PER_TOPIC])
            blocks.append(f'### Topic: "{topic}"\n{hl}')

        topics_json_keys = ", ".join(f'"{t}"' for t in topic_headlines)
        prompt = f"""You are a financial sentiment analyst. For EACH topic below, score stock-market sentiment.

{chr(10).join(blocks)}

Respond ONLY with valid JSON object (no markdown). Keys must be topic names exactly.
Each value:
{{
  "score": <-2 to 2 integer>,
  "label": <"매우부정"|"부정"|"중립"|"긍정"|"매우긍정">,
  "keywords": [<3-5 terms>],
  "reason": <one Korean sentence>
}}

Example shape: {{ {topics_json_keys} ... }}"""

        message = client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = _extract_message_text(message)
        parsed = _parse_claude_json(raw)
        if not isinstance(parsed, dict):
            raise ValueError("Claude batch response was not a JSON object")
        out = {}
        for topic, headlines in topic_headlines.items():
            item = parsed.get(topic, {})
            out[topic] = {
                "score": int(item.get("score", 0)),
                "label": item.get("label", "중립"),
                "keywords": item.get("keywords", []),
                "reason": item.get("reason", ""),
                "headlines_used": len(headlines),
            }
        return out
    except Exception as e:
        print(f"[WARN] Claude 배치 분석 실패: {e} → 토픽별 개별 호출로 폴백")
        return {
            topic: _claude_sentiment(topic, hl)
            for topic, hl in topic_headlines.items()
        }


def _store_topic_result(topic: str, sentiment: dict, headlines: list[str], now: datetime) -> dict:
    result = {
        **sentiment,
        "headlines": headlines,
        "cached": False,
        "analyzed_at": now.strftime("%H:%M"),
        "topic": topic,
    }
    _cache[topic] = {
        "result": result,
        "expires_at": now + timedelta(minutes=config.NEWS_FETCH_INTERVAL_MIN),
    }
    return result


def analyze_all_topics() -> dict[str, dict]:
    """모든 설정 토픽에 대해 감성 분석 수행 (선택 시 Claude 1회 배치)"""
    now = datetime.now(KST)
    results: dict[str, dict] = {}
    topic_headlines: dict[str, list[str]] = {}

    for topic in config.NEWS_TOPICS:
        if topic in _cache and now < _cache[topic]["expires_at"]:
            r = _cache[topic]["result"].copy()
            r["cached"] = True
            results[topic] = r
            continue

        print(f"  뉴스 수집: {topic}")
        if config.MOCK_MODE:
            headlines = _MOCK_NEWS_POOL.get(topic, [f"[MOCK] News about {topic}"])
        else:
            headlines = fetch_news_headlines(topic, max_items=config.NEWS_MAX_PER_TOPIC)

        if not headlines:
            results[topic] = {
                "score": 0, "label": "중립", "keywords": [],
                "reason": "수집된 뉴스 없음", "headlines": [],
                "cached": False, "analyzed_at": now.strftime("%H:%M"), "topic": topic,
            }
            continue
        topic_headlines[topic] = headlines

    use_batch = (
        topic_headlines
        and not config.MOCK_MODE
        and "여기에" not in config.ANTHROPIC_API_KEY
        and getattr(config, "CLAUDE_BATCH_SENTIMENT", True)
        and len(topic_headlines) > 1
    )

    batch_sentiments: dict[str, dict] = {}
    if use_batch:
        print("  Claude 배치 감성 분석 (1회 호출)...")
        batch_sentiments = _claude_sentiment_batch(topic_headlines)

    for topic, headlines in topic_headlines.items():
        if config.MOCK_MODE or "여기에" in config.ANTHROPIC_API_KEY:
            sentiment = _mock_sentiment(topic, headlines)
        elif topic in batch_sentiments:
            sentiment = batch_sentiments[topic]
        else:
            sentiment = _claude_sentiment(topic, headlines)
        results[topic] = _store_topic_result(topic, sentiment, headlines, now)

    return results


def get_stock_sentiment(stock_code: str, all_results: dict[str, dict]) -> dict:
    """
    종목 코드에 맞는 감성 점수를 집계.
    config.STOCK_TOPIC_MAP 우선, 없으면 keywords ↔ topic 부분 일치 폴백.
    """
    label_map = {2: "매우긍정", 1: "긍정", 0: "중립", -1: "부정", -2: "매우부정"}
    matched_scores: list[int] = []
    matched_reasons: list[str] = []
    matched_keywords: list[str] = []

    topic_map = getattr(config, "STOCK_TOPIC_MAP", {})
    mapped_topics = topic_map.get(stock_code, [])

    if mapped_topics:
        for topic in mapped_topics:
            result = all_results.get(topic)
            if result is None:
                continue
            matched_scores.append(result["score"])
            matched_reasons.append(result.get("reason", ""))
            matched_keywords.extend(result.get("keywords", []))
    else:
        stock_info = {**config.KR_STOCKS, **config.US_STOCKS}.get(stock_code, {})
        keywords = stock_info.get("keywords", [])
        for topic, result in all_results.items():
            if any(kw.lower() in topic.lower() for kw in keywords):
                matched_scores.append(result["score"])
                matched_reasons.append(result.get("reason", ""))
                matched_keywords.extend(result.get("keywords", []))

    if not matched_scores:
        return {"score": 0, "label": "중립", "keywords": [], "reason": "관련 뉴스 없음"}

    avg_score = sum(matched_scores) / len(matched_scores)
    rounded = round(avg_score)

    return {
        "score": rounded,
        "raw_score": avg_score,
        "label": label_map.get(rounded, "중립"),
        "keywords": list(set(matched_keywords))[:5],
        "reason": matched_reasons[0] if matched_reasons else "관련 뉴스 없음",
    }


def get_cache_status() -> list[dict]:
    """대시보드용: 현재 캐시 상태 조회"""
    now = datetime.now(KST)
    status = []
    for topic, cached in _cache.items():
        remaining = (cached["expires_at"] - now).total_seconds()
        status.append({
            "topic": topic,
            "score": cached["result"].get("score", 0),
            "label": cached["result"].get("label", "-"),
            "keywords": cached["result"].get("keywords", []),
            "reason": cached["result"].get("reason", ""),
            "expires_in_min": max(0, int(remaining / 60)),
            "analyzed_at": cached["result"].get("analyzed_at", "-"),
        })
    return status
