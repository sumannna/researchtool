"""
JANコード取得フロー
Step1: Serper API で Web 検索（上位5件のスニペット取得）
Step2: Claude API にスニペットを渡してJANコードを抽出
"""
import logging
import re

import anthropic
import httpx

from .config_loader import get_key

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Claude API プロンプトテンプレート（仕様 §12 に準拠）
# ──────────────────────────────────────────────
SYSTEM_PROMPT = """あなたはAmazon商品のJANコードを特定する専門家です。
与えられた検索結果のスニペットから、商品のJANコード（13桁の数字）を抽出してください。
JANコードが見つかった場合は数字のみ（例: 4901234567890）を返してください。
見つからない場合は「NOT_FOUND」のみを返してください。
それ以外の文字は一切出力しないでください。"""


def build_user_prompt(product_title: str, serper_results: list[dict]) -> str:
    snippets = "\n".join(
        f"[{i+1}] タイトル: {r.get('title', '')}\n    スニペット: {r.get('snippet', '')}"
        for i, r in enumerate(serper_results[:5])
    )
    return (
        f"商品名: {product_title}\n\n"
        f"検索結果:\n{snippets}\n\n"
        "この商品のJANコードを教えてください。"
    )


# ──────────────────────────────────────────────
# 商品名短縮ロジック（仕様 §2-4 に準拠）
# ──────────────────────────────────────────────
def shorten_product_name(title: str) -> str:
    """
    Amazon 商品名を短縮して JAN 検索用クエリを生成する。
    1. 【...】【 】[...] 内の補足説明を除去
    2. 容量・個数表記（500ml×24本など）は保持
    3. ブランド名＋製品名のみに絞る（目安：30文字以内）
    """
    cleaned = title

    # 【...】を除去
    cleaned = re.sub(r"【[^】]*】", "", cleaned)

    # [...] を除去
    cleaned = re.sub(r"\[[^\]]*\]", "", cleaned)

    # (...) は容量・個数表記以外を除去
    def _remove_paren(m: re.Match) -> str:
        content = m.group(0)
        if re.search(r"\d+\s*(ml|L|g|kg|個|本|枚|袋|箱|缶|×)", content, re.IGNORECASE):
            return content
        return ""

    cleaned = re.sub(r"\([^)]*\)", _remove_paren, cleaned)

    # 余分な空白を整理
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # 30文字以内に切り詰め（単語境界を優先）
    if len(cleaned) > 30:
        truncated = cleaned[:30]
        # スペースがあれば最後のスペースで切る
        if " " in truncated:
            truncated = truncated.rsplit(" ", 1)[0]
        cleaned = truncated

    return cleaned


# ──────────────────────────────────────────────
# Serper API
# ──────────────────────────────────────────────
async def search_serper(query: str) -> list[dict]:
    """Serper API で Google 検索し、上位5件の organic 結果を返す"""
    api_key = get_key("serper_api_key")
    if not api_key:
        logger.warning("Serper APIキーが未設定です")
        return []
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://google.serper.dev/search",
                headers={
                    "X-API-KEY": api_key,
                    "Content-Type": "application/json",
                },
                json={"q": query, "num": 5, "gl": "jp", "hl": "ja"},
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("organic", [])[:5]
    except Exception as e:
        logger.error("Serper API エラー: %s", e)
        return []


# ──────────────────────────────────────────────
# Claude API（JANコード抽出）
# ──────────────────────────────────────────────
async def extract_jan_with_claude(
    product_title: str, serper_results: list[dict]
) -> "str | None":
    """
    Claude API にスニペットを渡して JANコードを抽出する。
    入力トークン上限: 約 2000（仕様 §10）
    """
    api_key = get_key("claude_api_key")
    if not api_key:
        logger.warning("Claude APIキーが未設定です")
        return None
    if not serper_results:
        return None
    try:
        client = anthropic.AsyncAnthropic(api_key=api_key)
        user_prompt = build_user_prompt(product_title, serper_results)
        message = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        result = message.content[0].text.strip()
        logger.debug("Claude応答: %s", result)

        if result == "NOT_FOUND":
            return None

        # 13桁の数字ならそのまま返す
        if re.fullmatch(r"\d{13}", result):
            return result

        # 応答内に 13 桁の数字が含まれていれば抽出
        match = re.search(r"\d{13}", result)
        if match:
            return match.group(0)

        return None
    except Exception as e:
        logger.error("Claude API エラー: %s", e)
        return None


# ──────────────────────────────────────────────
# メインフロー
# ──────────────────────────────────────────────
async def resolve_jan(product_title: str) -> "str | None":
    """
    商品タイトルから JANコードを取得するメインフロー。
    Step1: Serper API で「{短縮タイトル} JANコード」を検索
    Step2: 結果がなければ「{短縮タイトル} JAN」で再試行
    Step3: Claude API でスニペットから JANコードを抽出
    """
    short_title = shorten_product_name(product_title)
    logger.info("JAN検索クエリ: %s JANコード", short_title)

    serper_results = await search_serper(f"{short_title} JANコード")
    if not serper_results:
        logger.debug("JANコードで結果なし。JAN で再試行")
        serper_results = await search_serper(f"{short_title} JAN")

    jan_code = await extract_jan_with_claude(product_title, serper_results)

    if jan_code:
        logger.info("JANコード取得成功: %s", jan_code)
    else:
        logger.info("JANコード取得不可: %.50s", product_title)

    return jan_code
