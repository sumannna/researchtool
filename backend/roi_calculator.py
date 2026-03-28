"""
ROI・利益率・FBA手数料計算
"""

# カテゴリ別販売手数料率（rootCategoryID → 料率）
REFERRAL_FEE_RATE: dict[int, float] = {
    2189494051: 0.08,  # ドラッグストア
    57035011:   0.08,  # ビューティー
    3828871:    0.10,  # ホーム＆キッチン
    2189514051: 0.08,  # 食品・飲料・お酒
    2201396051: 0.08,  # ペット用品
    14304371:   0.10,  # スポーツ＆アウトドア
    13312011:   0.10,  # おもちゃ
    2189707051: 0.10,  # 文房具・オフィス用品
    2189641051: 0.10,  # DIY・工具
    2151999051: 0.10,  # カー用品
}
DEFAULT_REFERRAL_FEE_RATE = 0.10

# FBA手数料テーブル（2024年4月改定後・税込、円）
FBA_FEE_TABLE: dict[str, int] = {
    "小型":    288,
    "標準1":   354,
    "標準2":   410,
    "標準3":   470,
    "標準4":   524,
    "大型1":   756,
    "大型2":   1040,
    "大型3":   1312,
    "大型4":   1640,
    "特大型1": 2117,
    "特大型2": 2700,
    "特大型3": 3700,
    "特大型4": 5625,
}


def classify_fba_size(dims: list[float], weight_kg: float) -> str:
    """商品寸法（降順リスト・cm）・重量（kg）からFBAサイズ区分を返す"""
    l, w, h = dims[0], dims[1], dims[2]
    if l <= 25 and w <= 18 and h <= 2 and weight_kg <= 0.3:
        return "小型"
    elif l <= 35 and w <= 30 and h <= 3.3 and weight_kg <= 1.0:
        return "標準1"
    elif l <= 45 and w <= 35 and h <= 20 and weight_kg <= 2.0:
        return "標準2"
    elif l <= 45 and w <= 35 and h <= 20 and weight_kg <= 5.0:
        return "標準3"
    elif l <= 45 and w <= 35 and h <= 20 and weight_kg <= 9.0:
        return "標準4"
    elif l <= 80 and w <= 60 and h <= 60 and weight_kg <= 10.0:
        return "大型1"
    elif l <= 100 and w <= 60 and h <= 60 and weight_kg <= 15.0:
        return "大型2"
    elif l <= 120 and w <= 80 and h <= 80 and weight_kg <= 20.0:
        return "大型3"
    elif l <= 150 and w <= 100 and h <= 100 and weight_kg <= 25.0:
        return "大型4"
    else:
        return "特大型1"


def calculate_fba_fee(product: dict) -> int:
    """
    KeepaデータからFBA手数料（円）を算出する。
    fbaFeesフィールドがあればそれを優先、なければサイズ区分テーブルで算出。
    """
    fba_fees = product.get("fbaFees")
    if fba_fees and fba_fees.get("pickAndPackFee", -1) != -1:
        return int(fba_fees["pickAndPackFee"])

    h = float(product.get("packageHeight") or 0)   # mm
    l = float(product.get("packageLength") or 0)   # mm
    w = float(product.get("packageWidth") or 0)    # mm
    weight_g = float(product.get("packageWeight") or 0)  # g

    h_cm, l_cm, w_cm = h / 10, l / 10, w / 10
    weight_kg = (weight_g + 150) / 1000  # 梱包資材 150g 加算

    dims = sorted([l_cm, w_cm, h_cm], reverse=True)
    size = classify_fba_size(dims, weight_kg)
    return FBA_FEE_TABLE.get(size, 500)


def get_referral_fee(product: dict, selling_price: int) -> int:
    """カテゴリ別販売手数料（円）を返す"""
    rate = REFERRAL_FEE_RATE.get(
        product.get("rootCategory"), DEFAULT_REFERRAL_FEE_RATE
    )
    return int(selling_price * rate)


def calculate_profit(
    amazon_price: float,
    buy_price: float,
    referral_fee: int,
    fba_fee: int,
) -> tuple[float, float, float]:
    """
    利益額・利益率・ROI を計算して返す。

    Returns:
        (profit, profit_rate, roi)
        profit      : 利益額（円）
        profit_rate : 利益率（%）= 利益額 ÷ 販売価格 × 100
        roi         : ROI（%）= 利益額 ÷ 仕入れ単価 × 100
    """
    profit = amazon_price - buy_price - referral_fee - fba_fee
    profit_rate = (profit / amazon_price * 100) if amazon_price > 0 else 0.0
    roi = (profit / buy_price * 100) if buy_price > 0 else 0.0
    return profit, profit_rate, roi
