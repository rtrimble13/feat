"""Cost of capital: CAPM and WACC."""

import pytest

from feat.domain.costofcapital import capm
from feat.domain.costofcapital.wacc import (
    WaccInputs,
    cost_of_debt_from_interest,
    wacc,
)


class TestCapm:
    def test_cost_of_equity(self):
        assert capm.cost_of_equity(0.042, 1.2, 0.05) == pytest.approx(0.102)

    def test_negative_erp_rejected(self):
        with pytest.raises(ValueError):
            capm.cost_of_equity(0.04, 1.0, -0.01)


class TestWacc:
    def test_market_value_weights(self):
        result = wacc(WaccInputs(
            market_value_equity=60, market_value_debt=40,
            cost_of_equity=0.10, cost_of_debt=0.05, tax_rate=0.25,
        ))
        assert result == pytest.approx(0.6 * 0.10 + 0.4 * 0.05 * 0.75)

    def test_zero_capital_rejected(self):
        with pytest.raises(ValueError):
            wacc(WaccInputs(0, 0, 0.1, 0.05, 0.25))

    def test_tax_rate_must_be_fraction(self):
        with pytest.raises(ValueError, match="fraction"):
            wacc(WaccInputs(60, 40, 0.1, 0.05, 21.0))  # 21 instead of 0.21

    def test_cost_of_debt_from_interest(self):
        assert cost_of_debt_from_interest(-1.5, 30) == pytest.approx(0.05)
        assert cost_of_debt_from_interest(1.5, None) is None
        assert cost_of_debt_from_interest(1.5, 0) is None
