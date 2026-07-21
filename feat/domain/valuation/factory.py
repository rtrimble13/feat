"""Factory for valuation strategies: name -> value() callable."""

from __future__ import annotations

from typing import Callable

from feat.domain.errors import AnalysisError, Result
from feat.domain.valuation import ValuationInputs, ValuationOutcome
from feat.domain.valuation import dcf_fcfe, dcf_fcff, ddm, residual_income, reverse_dcf

ValuationModel = Callable[[ValuationInputs], Result[ValuationOutcome, AnalysisError]]

_MODELS: dict[str, ValuationModel] = {
    "dcf-fcff": dcf_fcff.value,
    "dcf-fcfe": dcf_fcfe.value,
    "ddm": ddm.value,
    "residual-income": residual_income.value,
    "reverse-dcf": reverse_dcf.value,
}

MODEL_NAMES = sorted(_MODELS)


def build_valuation_model(name: str) -> ValuationModel:
    try:
        return _MODELS[name]
    except KeyError:
        raise ValueError(
            f"unknown valuation model {name!r}; choose from {', '.join(MODEL_NAMES)}"
        ) from None
