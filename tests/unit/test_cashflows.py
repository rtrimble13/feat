"""FCFF / FCFE reconstruction from raw statement figures."""

import pytest

from feat.domain.cashflows import fcfe, fcff


class TestFcff:
    def test_hand_computed(self):
        # 28 + 1*(1-0.2) - 8 = 20.8
        assert fcff(28.0, -1.0, 0.2, -8.0) == pytest.approx(20.8)

    def test_capex_sign_normalized(self):
        assert fcff(28.0, 1.0, 0.2, 8.0) == fcff(28.0, 1.0, 0.2, -8.0)

    def test_missing_ocf_or_capex_is_none(self):
        assert fcff(None, 1.0, 0.2, -8.0) is None
        assert fcff(28.0, 1.0, 0.2, None) is None

    def test_missing_interest_treated_as_zero_leg(self):
        # interest is an adjustment, not a gate: FCFF = OCF - capex
        assert fcff(28.0, None, 0.2, -8.0) == pytest.approx(20.0)


class TestFcfe:
    def test_hand_computed(self):
        # 28 - 8 + (-1) = 19
        assert fcfe(28.0, -8.0, -1.0) == pytest.approx(19.0)

    def test_missing_borrowing_treated_as_zero_leg(self):
        assert fcfe(28.0, -8.0, None) == pytest.approx(20.0)

    def test_missing_core_inputs_is_none(self):
        assert fcfe(None, -8.0, 0.0) is None
