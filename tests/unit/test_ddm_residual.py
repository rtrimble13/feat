"""DDM variants and the residual income model."""

import pytest

from feat.domain.errors import InvalidInput, MissingRequiredField
from feat.domain.valuation import ValuationInputs
from feat.domain.valuation import ddm, residual_income
from feat.domain.valuation.ddm import gordon, h_model, two_stage
from feat.domain.valuation.residual_income import residual_income_value


def inputs(**overrides) -> ValuationInputs:
    base = dict(
        ticker="TEST", price=50.0, dividends_per_share=2.0,
        book_value_per_share=30.0, roe=0.15, payout_ratio=0.4,
        growth=0.08, terminal_growth=0.03, cost_of_equity=0.09, horizon_years=5,
    )
    base.update(overrides)
    return ValuationInputs(**base)


class TestDdm:
    def test_gordon_textbook_value(self):
        # V = D1 / (r - g) = 2 / (0.08 - 0.03) = 40
        assert gordon(2.0, 0.08, 0.03) == pytest.approx(40.0)

    def test_gordon_rejects_g_above_r(self):
        with pytest.raises(ValueError):
            gordon(2.0, 0.03, 0.08)

    def test_two_stage_exceeds_gordon_when_high_growth(self):
        constant = two_stage(2.0, 0.03, 5, 0.03, 0.09)
        boosted = two_stage(2.0, 0.10, 5, 0.03, 0.09)
        assert boosted > constant
        # constant-growth two-stage collapses to Gordon on D0(1+g)
        assert constant == pytest.approx(gordon(2.0 * 1.03, 0.09, 0.03), rel=1e-9)

    def test_h_model_hand_computed(self):
        # (2*1.04 + 2*2.5*(0.10-0.04)) / (0.09-0.04) = (2.08+0.30)/0.05 = 47.6
        assert h_model(2.0, 0.10, 0.04, 2.5, 0.09) == pytest.approx(47.6)

    def test_strategy_requires_positive_dividend(self):
        result = ddm.value(inputs(dividends_per_share=None))
        assert result.is_err()
        assert isinstance(result.error, MissingRequiredField)
        result = ddm.value(inputs(dividends_per_share=0.0))
        assert result.is_err()

    def test_strategy_outputs_all_three_variants(self):
        outcome = ddm.value(inputs()).unwrap()
        assert outcome.details.keys() == {"two_stage", "h_model", "gordon"}
        assert outcome.fair_value_per_share == pytest.approx(outcome.details["two_stage"])


class TestResidualIncome:
    def test_roe_equal_to_cost_of_equity_is_book_value(self):
        # zero excess return -> value == current book value
        value, _ = residual_income_value(30.0, 0.10, 0.10, 0.4, 5)
        assert value == pytest.approx(30.0)

    def test_excess_returns_add_value(self):
        value, ri = residual_income_value(30.0, 0.15, 0.10, 0.4, 5)
        assert value > 30.0
        assert all(r > 0 for r in ri)

    def test_roe_below_cost_destroys_value(self):
        value, _ = residual_income_value(30.0, 0.05, 0.10, 0.4, 5)
        assert value < 30.0

    def test_persistence_bounds(self):
        with pytest.raises(ValueError):
            residual_income_value(30.0, 0.15, 0.10, 0.4, 5, persistence=1.0)

    def test_strategy_requires_positive_book_value(self):
        result = residual_income.value(inputs(book_value_per_share=-5.0))
        assert result.is_err()
        assert isinstance(result.error, MissingRequiredField)

    def test_strategy_rejects_nonpositive_result(self):
        # deeply negative spread and full retention drives value negative
        result = residual_income.value(inputs(roe=-0.8, payout_ratio=0.0,
                                              cost_of_equity=0.10, horizon_years=15))
        assert result.is_err()
        assert isinstance(result.error, InvalidInput)
