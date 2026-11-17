"""Тесты recommend_price. Запуск: python -m unittest -v (или pytest, если установлен)."""

import asyncio
import unittest
from decimal import Decimal

from starter import recommend_price, sample_fetch_offers


def source(offers, status="success"):
    """Фейковый async-источник с заданными предложениями."""
    async def fetch():
        return {"status": status, "offers": offers}
    return fetch


def offer(price, seller="PARTS", days=1):
    return {"seller": seller, "price": Decimal(price), "delivery_days": days}


class RecommendPriceTest(unittest.IsolatedAsyncioTestCase):

    # --- обычный расчёт ---

    async def test_sample_from_task(self):
        """Пример из задания: myshop и SLOW отброшены, 4800 * 0.985 = 4728.00."""
        res = await recommend_price(
            sample_fetch_offers, Decimal("4900.00"), Decimal("4500.00"))
        self.assertEqual(res["price"], Decimal("4728.00"))
        self.assertIsInstance(res["price"], Decimal)
        self.assertEqual(res["decision"], "APPLY")

    async def test_rounds_down_to_kopeck(self):
        """999.99 * 0.985 = 984.99015 -> 984.99 (вниз, не по правилам округления)."""
        fetch = source([offer("999.99"), offer("1500.00")])
        res = await recommend_price(fetch, Decimal("1000.00"), Decimal("1.00"))
        self.assertEqual(res["price"], Decimal("984.99"))

    async def test_min_price_floor(self):
        fetch = source([offer("1000.00")])
        res = await recommend_price(fetch, Decimal("1000.00"), Decimal("990.00"))
        self.assertEqual(res["price"], Decimal("990.00"))
        self.assertEqual(res["decision"], "APPLY")

    # --- фильтрация ---

    async def test_filters_own_shop_any_case_and_unknown_delivery(self):
        fetch = source([
            offer("100.00", seller="MyShop"),
            offer("200.00", days=None),
            offer("300.00", days=7),
            offer("1000.00", days=6),   # ровно 6 дней — подходит
        ])
        res = await recommend_price(fetch, Decimal("1000.00"), Decimal("1.00"))
        self.assertEqual(res["price"], Decimal("985.00"))

    async def test_no_suitable_offers_holds_even_below_min(self):
        fetch = source([offer("100.00", seller="MYSHOP"), offer("200.00", days=None)])
        res = await recommend_price(fetch, Decimal("400.00"), Decimal("500.00"))
        self.assertEqual((res["price"], res["decision"]), (Decimal("400.00"), "HOLD"))

    # --- сбои источника ---

    async def test_timeout_holds(self):
        async def slow():
            await asyncio.sleep(5)
        res = await recommend_price(slow, Decimal("100.00"), Decimal("50.00"), timeout_s=0.05)
        self.assertEqual((res["price"], res["decision"]), (Decimal("100.00"), "HOLD"))

    async def test_exception_holds(self):
        async def broken():
            raise ConnectionError("down")
        res = await recommend_price(broken, Decimal("100.00"), Decimal("50.00"))
        self.assertEqual((res["price"], res["decision"]), (Decimal("100.00"), "HOLD"))

    async def test_partial_status_holds(self):
        fetch = source([offer("90.00")], status="partial")
        res = await recommend_price(fetch, Decimal("100.00"), Decimal("50.00"))
        self.assertEqual((res["price"], res["decision"]), (Decimal("100.00"), "HOLD"))

    # --- граница 30% ---

    async def test_exact_boundary_both_sides(self):
        """Рекомендация 1300.00 и 700.00 при текущей 1000.00 — ровно ±30%, APPLY."""
        for competitor, expected in [("1319.80", "1300.00"), ("710.66", "700.00")]:
            fetch = source([offer(competitor)])
            res = await recommend_price(fetch, Decimal("1000.00"), Decimal("1.00"))
            self.assertEqual(res["price"], Decimal(expected))
            self.assertEqual(res["decision"], "APPLY", competitor)

    async def test_more_than_30_percent_is_review(self):
        fetch = source([offer("1319.81")])          # 1300.0128 -> 1300.01
        res = await recommend_price(fetch, Decimal("1000.00"), Decimal("1.00"))
        self.assertEqual(res["price"], Decimal("1300.01"))
        self.assertEqual(res["decision"], "REVIEW")


if __name__ == "__main__":
    unittest.main()
