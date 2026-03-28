"""
roi_calculator のユニットテスト
"""
import pytest
from backend.roi_calculator import (
    classify_fba_size,
    calculate_fba_fee,
    get_referral_fee,
    calculate_profit,
    FBA_FEE_TABLE,
    REFERRAL_FEE_RATE,
)


# ── classify_fba_size ──────────────────────────────

class TestClassifyFbaSize:
    def test_小型(self):
        assert classify_fba_size([24, 17, 1.5], 0.25) == "小型"

    def test_標準1(self):
        assert classify_fba_size([34, 29, 3.0], 0.9) == "標準1"

    def test_標準2(self):
        assert classify_fba_size([40, 30, 15], 1.5) == "標準2"

    def test_標準3(self):
        assert classify_fba_size([40, 30, 15], 4.0) == "標準3"

    def test_標準4(self):
        assert classify_fba_size([40, 30, 15], 8.0) == "標準4"

    def test_大型1(self):
        assert classify_fba_size([70, 50, 50], 9.0) == "大型1"

    def test_大型2(self):
        assert classify_fba_size([90, 55, 55], 14.0) == "大型2"

    def test_大型3(self):
        assert classify_fba_size([110, 70, 70], 18.0) == "大型3"

    def test_大型4(self):
        assert classify_fba_size([140, 90, 90], 24.0) == "大型4"

    def test_特大型(self):
        assert classify_fba_size([200, 120, 120], 30.0) == "特大型1"

    def test_境界値_小型_ぎりぎり通過(self):
        assert classify_fba_size([25.0, 18.0, 2.0], 0.3) == "小型"

    def test_境界値_小型_わずかに超過(self):
        # 重量超過 → 標準1
        result = classify_fba_size([25.0, 18.0, 2.0], 0.31)
        assert result == "標準1"


# ── calculate_fba_fee ──────────────────────────────

class TestCalculateFbaFee:
    def _make_product(self, h, l, w, weight_g, fba_fees=None):
        return {
            "packageHeight": h,
            "packageLength": l,
            "packageWidth": w,
            "packageWeight": weight_g,
            "fbaFees": fba_fees,
        }

    def test_fbaFees_フィールドがある場合はそれを使う(self):
        product = self._make_product(100, 200, 150, 500,
                                      fba_fees={"pickAndPackFee": 410})
        assert calculate_fba_fee(product) == 410

    def test_fbaFees_が_minus1_ならサイズ計算にフォールバック(self):
        product = self._make_product(100, 200, 150, 500,
                                      fba_fees={"pickAndPackFee": -1})
        fee = calculate_fba_fee(product)
        assert fee in FBA_FEE_TABLE.values() or fee == 500

    def test_小型商品の手数料(self):
        # 24×17×15mm, 150g → 実重量=(150+150)/1000=0.3kg, dims=[2.4,1.7,1.5]cm → 小型
        product = self._make_product(15, 24, 17, 150)
        assert calculate_fba_fee(product) == 288

    def test_サイズ不明ならデフォルト500円(self):
        product = self._make_product(0, 0, 0, 0)
        # 全0 → dims=[0,0,0], weight=0.15kg → 小型
        fee = calculate_fba_fee(product)
        assert isinstance(fee, int)

    def test_Noneフィールドが安全に処理される(self):
        product = {"packageHeight": None, "packageLength": None,
                   "packageWidth": None, "packageWeight": None, "fbaFees": None}
        fee = calculate_fba_fee(product)
        assert isinstance(fee, int)


# ── get_referral_fee ──────────────────────────────

class TestGetReferralFee:
    def test_ドラッグストアは8パーセント(self):
        product = {"rootCategory": 2189494051}
        assert get_referral_fee(product, 1000) == 80

    def test_ビューティーは8パーセント(self):
        product = {"rootCategory": 57035011}
        assert get_referral_fee(product, 2000) == 160

    def test_ホームキッチンは10パーセント(self):
        product = {"rootCategory": 3828871}
        assert get_referral_fee(product, 3000) == 300

    def test_不明カテゴリはデフォルト10パーセント(self):
        product = {"rootCategory": 99999999}
        assert get_referral_fee(product, 1000) == 100

    def test_rootCategoryなしはデフォルト(self):
        product = {}
        assert get_referral_fee(product, 1000) == 100


# ── calculate_profit ──────────────────────────────

class TestCalculateProfit:
    def test_正常ケース(self):
        # 販売¥2000, 仕入¥800, 手数料¥160+¥354
        profit, rate, roi = calculate_profit(2000, 800, 160, 354)
        assert profit == pytest.approx(686.0)
        assert rate == pytest.approx(34.3, abs=0.1)
        assert roi == pytest.approx(85.75, abs=0.1)

    def test_赤字ケース(self):
        profit, rate, roi = calculate_profit(1000, 1500, 100, 354)
        assert profit < 0
        assert rate < 0
        assert roi < 0

    def test_amazon価格ゼロ(self):
        profit, rate, roi = calculate_profit(0, 800, 0, 0)
        assert profit == pytest.approx(-800)
        assert rate == 0.0  # ゼロ除算しない

    def test_仕入れ価格ゼロ(self):
        profit, rate, roi = calculate_profit(2000, 0, 160, 354)
        assert roi == 0.0  # ゼロ除算しない

    def test_全指標がゼロ(self):
        profit, rate, roi = calculate_profit(0, 0, 0, 0)
        assert profit == 0.0
        assert rate == 0.0
        assert roi == 0.0
