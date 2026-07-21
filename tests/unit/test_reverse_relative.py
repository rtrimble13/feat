"""Reverse DCF inversion and relative-valuation multiples."""

import pytest

from feat.domain.valuation import ValuationInputs
from feat.domain.valuation import dcf_fcff, reverse_dcf
from feat.domain.valuation.factory import MODEL_NAMES, build_valuation_model
from feat.domain.valuation.relative import (
    MultipleInputs,
    compute_multiples,
    enterprise_value,
    implied_value_per_share,
    median,
    peer_median_multiples,
)


def inputs(**overrides) -> ValuationInputs:
    base = dict(
        ticker="TEST", price=100.0, shares_diluted=10.0, net_debt=10.0,
        base_fcff=20.8, growth=0.08, terminal_growth=0.025, wacc=0.09,
        cost_of_equity=0.10, horizon_years=5,
    )
    base.update(overrides)
    return ValuationInputs(**base)


class TestReverseDcf:
    def test_inversion_recovers_known_growth(self):
        # price the DCF at g=7%, then invert: implied growth must be ~7%
        target_growth = 0.07
        fair = dcf_fcff.value(inputs(growth=target_growth)).unwrap().fair_value_per_share
        result = reverse_dcf.value(inputs(price=fair))
        assert result.is_ok()
        assert result.unwrap().details["implied_growth"] == pytest.approx(
            target_growth, abs=1e-4
        )

    def test_unreachable_price_reports_invalid(self):
        result = reverse_dcf.value(inputs(price=1e9))
        assert result.is_err()

    def test_requires_price(self):
        result = reverse_dcf.value(inputs(price=None))
        assert result.is_err()


class TestRelativeMath:
    def test_enterprise_value(self):
        assert enterprise_value(100, 10) == 110
        assert enterprise_value(None, 10) is None

    def test_multiples_hand_checked(self):
        multiples = compute_multiples(MultipleInputs(
            price=100.0, market_cap=1000.0, net_debt=100.0, eps_diluted=5.0,
            book_value_per_share=25.0, revenue=500.0, ebitda=110.0, ebit=90.0,
            fcf=80.0, dividends_per_share=2.0, growth=0.10,
        ))
        assert multiples["pe"] == pytest.approx(20.0)
        assert multiples["pb"] == pytest.approx(4.0)
        assert multiples["ev_ebitda"] == pytest.approx(1100 / 110)
        assert multiples["dividend_yield"] == pytest.approx(0.02)
        assert multiples["peg"] == pytest.approx(20.0 / 10.0)

    def test_negative_earnings_yield_no_multiple(self):
        multiples = compute_multiples(MultipleInputs(price=100.0, eps_diluted=-2.0))
        assert multiples["pe"] is None  # meaningless, not negative

    def test_median_odd_even(self):
        assert median([3.0, 1.0, 2.0]) == 2.0
        assert median([4.0, 1.0, 2.0, 3.0]) == 2.5
        assert median([]) is None

    def test_peer_medians_skip_missing(self):
        medians = peer_median_multiples([
            {"pe": 10.0, "pb": None}, {"pe": 20.0, "pb": 3.0}, {"pe": None, "pb": 5.0},
        ])
        assert medians["pe"] == 15.0
        assert medians["pb"] == 4.0

    def test_implied_value(self):
        assert implied_value_per_share(15.0, 5.0) == 75.0
        assert implied_value_per_share(15.0, -1.0) is None


class TestFactory:
    def test_all_registered_models_resolve(self):
        for name in MODEL_NAMES:
            assert callable(build_valuation_model(name))

    def test_unknown_model_lists_choices(self):
        with pytest.raises(ValueError, match="dcf-fcff"):
            build_valuation_model("magic-8-ball")
