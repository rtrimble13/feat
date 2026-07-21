"""DCF machinery and the FCFF/FCFE strategies."""

import pytest

from feat.domain.errors import InvalidInput, MissingRequiredField
from feat.domain.valuation import ValuationInputs, margin_of_safety
from feat.domain.valuation.dcf import (
    growth_path,
    present_value,
    project_flows,
    run_dcf,
    terminal_value_exit_multiple,
    terminal_value_perpetuity,
)
from feat.domain.valuation import dcf_fcfe, dcf_fcff


def inputs(**overrides) -> ValuationInputs:
    base = dict(
        ticker="TEST", price=100.0, shares_diluted=10.0, net_debt=10.0,
        base_fcff=20.8, base_fcfe=19.0, base_ebitda=30.0,
        growth=0.08, terminal_growth=0.025, wacc=0.09, cost_of_equity=0.10,
        horizon_years=5,
    )
    base.update(overrides)
    return ValuationInputs(**base)


class TestDcfCore:
    def test_growth_path_fades_linearly(self):
        assert growth_path(0.10, 0.02, 5) == pytest.approx([0.10, 0.08, 0.06, 0.04, 0.02])

    def test_growth_path_single_year(self):
        assert growth_path(0.10, 0.02, 1) == [0.10]

    def test_project_flows_compounds(self):
        assert project_flows(100, [0.10, 0.10]) == pytest.approx([110.0, 121.0])

    def test_terminal_perpetuity_known_value(self):
        # 100 * 1.02 / (0.10 - 0.02) = 1275
        assert terminal_value_perpetuity(100, 0.10, 0.02) == pytest.approx(1275.0)

    def test_terminal_perpetuity_rejects_r_below_g(self):
        with pytest.raises(ValueError, match="must exceed"):
            terminal_value_perpetuity(100, 0.02, 0.03)

    def test_present_value_hand_computed(self):
        # flows [110], TV 1275 at r=10%: (110 + 1275) / 1.1
        assert present_value([110], 1275, 0.10) == pytest.approx(1385 / 1.1)

    def test_exit_multiple_tv(self):
        assert terminal_value_exit_multiple(50, 12) == 600
        with pytest.raises(ValueError):
            terminal_value_exit_multiple(50, 0)

    def test_run_dcf_dual_terminal_values(self):
        core = run_dcf(100, 0.05, 0.02, 0.09, 5, exit_metric_base=150, exit_multiple=10)
        assert core.tv_exit is not None and core.pv_exit is not None
        assert core.tv_perpetuity > 0
        assert len(core.projected_flows) == 5
        # exit metric grows on the same path as the flows
        assert core.tv_exit == pytest.approx(core.projected_flows[-1] / 100 * 150 * 10)


class TestFcffModel:
    def test_values_and_reports_assumptions(self):
        result = dcf_fcff.value(inputs())
        assert result.is_ok()
        outcome = result.unwrap()
        assert outcome.fair_value_per_share > 0
        assert outcome.assumptions["wacc"] == 0.09
        assert outcome.details["equity_value"] == pytest.approx(
            outcome.details["enterprise_value"] - 10.0
        )
        assert outcome.margin_of_safety == pytest.approx(
            1 - 100.0 / outcome.fair_value_per_share
        )

    def test_exit_multiple_produces_alt_value(self):
        result = dcf_fcff.value(inputs(exit_ev_ebitda=12.0))
        assert result.unwrap().fair_value_alt is not None

    def test_negative_fcff_is_invalid_not_a_number(self):
        result = dcf_fcff.value(inputs(base_fcff=-5.0))
        assert result.is_err()
        assert isinstance(result.error, InvalidInput)

    def test_missing_fcff_flagged(self):
        result = dcf_fcff.value(inputs(base_fcff=None))
        assert result.is_err()
        assert isinstance(result.error, MissingRequiredField)

    def test_wacc_below_terminal_growth_rejected(self):
        result = dcf_fcff.value(inputs(wacc=0.02))
        assert result.is_err()
        assert isinstance(result.error, InvalidInput)


class TestFcfeModel:
    def test_equity_direct_no_net_debt_needed(self):
        result = dcf_fcfe.value(inputs(net_debt=None))
        assert result.is_ok()

    def test_discounts_at_cost_of_equity(self):
        low = dcf_fcfe.value(inputs(cost_of_equity=0.09)).unwrap()
        high = dcf_fcfe.value(inputs(cost_of_equity=0.12)).unwrap()
        assert low.fair_value_per_share > high.fair_value_per_share


class TestMarginOfSafety:
    def test_sign_convention(self):
        assert margin_of_safety(80, 100) == pytest.approx(0.2)
        assert margin_of_safety(120, 100) == pytest.approx(-0.2)
        assert margin_of_safety(None, 100) is None
        assert margin_of_safety(80, 0) is None
