"""Quality and forensic scores."""

import dataclasses

import pytest

from feat.domain.quality.altman import altman_z
from feat.domain.quality.beneish import BeneishPeriod, beneish_m
from feat.domain.quality.piotroski import PiotroskiInputs, piotroski_f


def perfect_piotroski() -> PiotroskiInputs:
    return PiotroskiInputs(
        net_income=20, operating_cash_flow=25, total_assets=100,
        prior_total_assets=100, prior_net_income=10,
        long_term_debt=10, prior_long_term_debt=20,
        current_assets=50, current_liabilities=20,
        prior_current_assets=40, prior_current_liabilities=20,
        shares_out=100, prior_shares_out=100,
        gross_profit=40, revenue=100, prior_gross_profit=30, prior_revenue=90,
    )


class TestPiotroski:
    def test_perfect_nine(self):
        score = piotroski_f(perfect_piotroski())
        assert score.score == 9
        assert score.evaluated == 9

    def test_missing_signal_skipped_not_zeroed(self):
        inputs = dataclasses.replace(perfect_piotroski(),
                                     long_term_debt=None, prior_long_term_debt=None)
        score = piotroski_f(inputs)
        assert score.evaluated == 8
        assert score.signals["leverage_decreased"] is None
        assert score.score == 8  # the other eight still pass

    def test_dilution_fails_signal(self):
        inputs = dataclasses.replace(perfect_piotroski(), shares_out=110)
        assert piotroski_f(inputs).signals["no_dilution"] is False


class TestAltman:
    def test_hand_computed_grey_zone(self):
        # A=0.2 B=0.3 C=0.15 D=1.0 E=1.0 -> Z=2.755 (grey)
        result = altman_z(
            total_current_assets=40, total_current_liabilities=20, total_assets=100,
            retained_earnings=30, ebit=15, market_cap=60, total_liabilities=60,
            revenue=100,
        )
        assert result is not None
        assert result.z == pytest.approx(2.755)
        assert result.zone == "grey"

    def test_zones(self):
        strong = altman_z(60, 10, 100, 60, 25, 300, 40, 150)
        assert strong is not None and strong.zone == "safe"
        weak = altman_z(20, 40, 100, -20, -5, 10, 90, 50)
        assert weak is not None and weak.zone == "distress"

    def test_missing_component_returns_none(self):
        assert altman_z(40, 20, 100, None, 15, 60, 60, 100) is None


class TestBeneish:
    @staticmethod
    def period(**overrides) -> BeneishPeriod:
        base = dict(
            receivables=10, revenue=100, gross_profit=40, total_assets=120,
            current_assets=45, ppe_net=30, depreciation_amortization=5,
            sga_expense=10, total_debt=30, total_liabilities=60,
            net_income=19.2, operating_cash_flow=28,
        )
        base.update(overrides)
        return BeneishPeriod(**base)

    def test_steady_state_not_flagged(self):
        # identical periods: every index 1, TATA negative (cash > earnings)
        result = beneish_m(self.period(), self.period())
        assert result is not None
        assert not result.flag
        assert result.indices["DSRI"] == pytest.approx(1.0)

    def test_aggressive_receivables_raises_score(self):
        stretched = self.period(receivables=30, net_income=35, operating_cash_flow=10)
        baseline = beneish_m(self.period(), self.period())
        result = beneish_m(stretched, self.period())
        assert result is not None and baseline is not None
        assert result.m_score > baseline.m_score

    def test_missing_input_yields_none_not_partial_score(self):
        assert beneish_m(self.period(sga_expense=None), self.period()) is None
