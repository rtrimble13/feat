"""Value objects: validation and invariants."""

import pytest

from feat.domain.values import (
    MISSING,
    Money,
    Percent,
    ShareBasis,
    ShareCount,
    Ticker,
    amount_of,
    is_missing,
)


class TestTicker:
    def test_uppercases_and_strips(self):
        assert Ticker(" aapl ").symbol == "AAPL"

    def test_allows_exchange_suffix_and_class_shares(self):
        assert Ticker("RY.TO").symbol == "RY.TO"
        assert Ticker("BRK-B").symbol == "BRK-B"

    @pytest.mark.parametrize("bad", ["", "  ", "; rm -rf /", "AAPL;ls", "A" * 13,
                                     "../etc", "AAPL$", "A B"])
    def test_rejects_injection_and_garbage(self, bad):
        with pytest.raises(ValueError):
            Ticker(bad)


class TestMoney:
    def test_arithmetic_same_currency(self):
        assert (Money(10) + Money(5)).amount == 15
        assert (Money(10) - Money(5)).amount == 5
        assert (Money(10) * 2).amount == 20
        assert (Money(10) / Money(4)) == 2.5

    def test_refuses_currency_mixing(self):
        with pytest.raises(ValueError, match="mix currencies"):
            Money(1, "USD") + Money(1, "EUR")

    def test_rejects_invalid_currency(self):
        with pytest.raises(ValueError):
            Money(1, "US")

    def test_rejects_non_numeric(self):
        with pytest.raises(TypeError):
            Money("100")  # type: ignore[arg-type]

    def test_division_by_zero_raises(self):
        with pytest.raises(ZeroDivisionError):
            Money(1) / 0


class TestMissing:
    def test_singleton_and_falsy(self):
        assert is_missing(MISSING)
        assert is_missing(None)
        assert not is_missing(Money(0))
        assert not MISSING

    def test_amount_of_never_zeroes_missing(self):
        assert amount_of(MISSING) is None
        assert amount_of(Money(0)) == 0.0


class TestPercent:
    def test_no_fraction_percent_confusion(self):
        assert Percent.from_percent(15).fraction == pytest.approx(0.15)
        assert Percent.from_fraction(0.15).as_percent == pytest.approx(15.0)
        assert str(Percent.from_fraction(0.15)) == "15.00%"


class TestShareCount:
    def test_basis_distinguished(self):
        basic = ShareCount(100, ShareBasis.BASIC)
        diluted = ShareCount(105, ShareBasis.DILUTED)
        assert basic.basis is not diluted.basis

    def test_negative_rejected(self):
        with pytest.raises(ValueError):
            ShareCount(-1, ShareBasis.BASIC)
