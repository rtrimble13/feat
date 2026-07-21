"""Scenarios, sensitivity grids and Monte Carlo determinism."""

import pytest

from feat.domain.forecasting.monte_carlo import simulate
from feat.domain.forecasting.scenarios import apply_scenario
from feat.domain.forecasting.sensitivity import wacc_growth_grid
from feat.domain.valuation import ValuationInputs
from feat.domain.valuation.factory import build_valuation_model


def inputs(**overrides) -> ValuationInputs:
    base = dict(
        ticker="TEST", price=100.0, shares_diluted=10.0, net_debt=10.0,
        base_fcff=20.8, base_fcfe=19.0, growth=0.08, terminal_growth=0.025,
        wacc=0.09, cost_of_equity=0.10, horizon_years=5,
    )
    base.update(overrides)
    return ValuationInputs(**base)


class TestScenarios:
    def test_base_is_identity(self):
        assert apply_scenario(inputs(), "base") == inputs()

    def test_bull_raises_growth_lowers_discount(self):
        bull = apply_scenario(inputs(), "bull")
        assert bull.growth > inputs().growth
        assert bull.wacc < inputs().wacc

    def test_bear_moves_opposite(self):
        bear = apply_scenario(inputs(), "bear")
        assert bear.growth < inputs().growth
        assert bear.wacc > inputs().wacc

    def test_unknown_scenario_rejected(self):
        with pytest.raises(ValueError, match="bull"):
            apply_scenario(inputs(), "sideways")


class TestSensitivity:
    def test_grid_shape_and_monotonicity(self):
        model = build_valuation_model("dcf-fcff")
        grid = wacc_growth_grid(model, inputs(), steps=2)
        assert len(grid.wacc_values) == 5
        assert len(grid.fair_values) == 5 and all(len(r) == 5 for r in grid.fair_values)
        center = grid.fair_values[2][2]
        # higher wacc, same growth -> lower value; higher growth, same wacc -> higher value
        assert grid.fair_values[4][2] < center < grid.fair_values[0][2]
        assert grid.fair_values[2][0] < center < grid.fair_values[2][4]

    def test_degenerate_cells_are_none(self):
        model = build_valuation_model("dcf-fcff")
        grid = wacc_growth_grid(model, inputs(wacc=0.03, terminal_growth=0.025),
                                wacc_step=0.01, growth_step=0.01, steps=2)
        assert any(cell is None for row in grid.fair_values for cell in row)


class TestMonteCarlo:
    def test_same_seed_reproduces_exactly(self):
        model = build_valuation_model("dcf-fcff")
        a = simulate(model, inputs(), draws=500, seed=7)
        b = simulate(model, inputs(), draws=500, seed=7)
        assert a == b

    def test_different_seed_differs(self):
        model = build_valuation_model("dcf-fcff")
        a = simulate(model, inputs(), draws=500, seed=7)
        b = simulate(model, inputs(), draws=500, seed=8)
        assert a.percentiles != b.percentiles

    def test_percentiles_ordered_and_probability_bounded(self):
        model = build_valuation_model("dcf-fcff")
        result = simulate(model, inputs(), draws=500, seed=7)
        p = result.percentiles
        assert p[5] <= p[25] <= p[50] <= p[75] <= p[95]
        assert 0.0 <= result.prob_below_price <= 1.0

    def test_minimum_draws_enforced(self):
        model = build_valuation_model("dcf-fcff")
        with pytest.raises(ValueError, match="100 draws"):
            simulate(model, inputs(), draws=10, seed=7)
