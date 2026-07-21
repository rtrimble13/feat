"""Use-case: ValueCompany — assemble inputs, run a valuation strategy,
attach the FMP reference DCF cross-check, sensitivity and Monte Carlo."""

from __future__ import annotations

from dataclasses import dataclass

from feat.domain.costofcapital import capm
from feat.domain.costofcapital.wacc import WaccInputs, cost_of_debt_from_interest, wacc
from feat.domain.entities import Company, FinancialHistory
from feat.domain.errors import (
    AnalysisError,
    Err,
    InsufficientHistory,
    Ok,
    Result,
)
from feat.domain.forecasting.monte_carlo import MonteCarloResult, simulate
from feat.domain.forecasting.scenarios import apply_scenario
from feat.domain.forecasting.sensitivity import SensitivityGrid, wacc_growth_grid
from feat.domain.ports import FundamentalsRepository, PriceRepository
from feat.domain.valuation import ValuationInputs, ValuationOutcome, margin_of_safety
from feat.domain.valuation.factory import build_valuation_model
from feat.domain.valuation.relative import (
    MultipleInputs,
    compute_multiples,
    implied_value_per_share,
    peer_median_multiples,
)
from feat.domain.values import PeriodType, Ticker, amount_of
from feat.infra.config import FeatConfig
from feat.services import derive

MAX_RELATIVE_PEERS = 5


@dataclass(frozen=True, slots=True)
class ValuationOverrides:
    """Analyst flag overrides; None means 'use the derived default'."""

    wacc: float | None = None
    cost_of_equity: float | None = None
    growth: float | None = None
    terminal_growth: float | None = None
    horizon_years: int | None = None
    exit_ev_ebitda: float | None = None


@dataclass(frozen=True, slots=True)
class ValuationReport:
    company: Company
    outcome: ValuationOutcome
    scenario: str
    fmp_reference_dcf: float | None
    sensitivity: SensitivityGrid | None = None
    monte_carlo: MonteCarloResult | None = None


class ValueCompany:
    def __init__(
        self,
        fundamentals: FundamentalsRepository,
        prices: PriceRepository,
        config: FeatConfig,
    ) -> None:
        self._fundamentals = fundamentals
        self._prices = prices
        self._config = config

    def run(
        self,
        ticker: Ticker,
        model_name: str,
        overrides: ValuationOverrides = ValuationOverrides(),
        scenario: str = "base",
        monte_carlo_draws: int = 0,
        monte_carlo_seed: int = 42,
        with_sensitivity: bool = True,
    ) -> Result[ValuationReport, AnalysisError]:
        company_result = self._fundamentals.get_company(ticker)
        if company_result.is_err():
            return company_result
        company = company_result.unwrap()

        history_result = self._fundamentals.get_history(
            ticker, PeriodType.ANNUAL, self._config.default_years_history
        )
        if history_result.is_err():
            return history_result
        history = history_result.unwrap()
        if len(history) < 2:
            return Err(InsufficientHistory(
                f"{ticker}: need at least 2 annual periods to value, have {len(history)}"
            ))

        inputs = self._build_inputs(company, history, overrides)
        inputs = apply_scenario(inputs, scenario)

        if model_name == "relative":
            outcome_result = self._relative(company, history, inputs)
        else:
            model = build_valuation_model(model_name)
            outcome_result = model(inputs)
        if outcome_result.is_err():
            return outcome_result
        outcome = outcome_result.unwrap()

        reference = None
        ref_result = self._fundamentals.get_reference_dcf(ticker)
        if ref_result.is_ok():  # reference is a cross-check; its absence never fails the run
            reference = ref_result.unwrap()

        sensitivity = None
        if with_sensitivity and model_name in {"dcf-fcff", "dcf-fcfe", "ddm", "residual-income"}:
            sensitivity = wacc_growth_grid(build_valuation_model(model_name), inputs)

        monte_carlo = None
        if monte_carlo_draws > 0 and model_name in {"dcf-fcff", "dcf-fcfe"}:
            monte_carlo = simulate(
                build_valuation_model(model_name), inputs,
                draws=monte_carlo_draws, seed=monte_carlo_seed,
            )

        return Ok(ValuationReport(
            company=company,
            outcome=outcome,
            scenario=scenario,
            fmp_reference_dcf=reference,
            sensitivity=sensitivity,
            monte_carlo=monte_carlo,
        ))

    # -- input assembly ---------------------------------------------------

    def _build_inputs(
        self,
        company: Company,
        history: FinancialHistory,
        overrides: ValuationOverrides,
    ) -> ValuationInputs:
        cfg = self._config
        latest = history.statements[0]
        prior = history.statements[1]
        rows = derive.ratio_rows(latest, prior)

        price = amount_of(company.price)
        shares = latest.income.weighted_shares_diluted or company.shares_outstanding
        market_cap = amount_of(company.market_cap)
        if market_cap is None and price is not None and shares is not None:
            market_cap = price * shares

        beta = company.beta if company.beta is not None else 1.0
        cost_of_equity = capm.cost_of_equity(
            cfg.risk_free_rate, beta, cfg.equity_risk_premium
        )

        total_debt = amount_of(latest.balance.total_debt)
        cost_of_debt = cost_of_debt_from_interest(
            amount_of(latest.income.interest_expense), total_debt
        )
        if cost_of_debt is None:
            cost_of_debt = cfg.risk_free_rate + 0.02  # rating-agnostic default spread
        tax_rate = rows["effective_tax_rate"]
        if tax_rate is None:
            tax_rate = cfg.default_tax_rate

        if market_cap is not None and market_cap > 0:
            derived_wacc = wacc(WaccInputs(
                market_value_equity=market_cap,
                market_value_debt=total_debt if total_debt is not None else 0.0,
                cost_of_equity=cost_of_equity,
                cost_of_debt=cost_of_debt,
                tax_rate=tax_rate,
            ))
        else:
            derived_wacc = cost_of_equity

        revenue_series = history.trend("revenue")
        growth = derive.historical_growth(revenue_series)
        if growth is None:
            growth = 0.05
        growth = min(max(growth, -0.20), 0.25)  # clamp to plausible forecast range

        return ValuationInputs(
            ticker=company.ticker.symbol,
            currency=company.currency,
            price=price,
            shares_diluted=shares,
            net_debt=derive.net_debt_of(latest),
            base_fcff=derive.fcff_of(latest),
            base_fcfe=derive.fcfe_of(latest),
            base_ebitda=amount_of(latest.income.ebitda),
            dividends_per_share=rows["dividends_per_share"],
            eps=latest.income.eps_diluted,
            book_value_per_share=rows["book_value_per_share"],
            roe=rows["roe"],
            payout_ratio=derive.payout_ratio_of(latest),
            growth=overrides.growth if overrides.growth is not None else growth,
            terminal_growth=(
                overrides.terminal_growth
                if overrides.terminal_growth is not None
                else cfg.default_terminal_growth
            ),
            wacc=overrides.wacc if overrides.wacc is not None else derived_wacc,
            cost_of_equity=(
                overrides.cost_of_equity
                if overrides.cost_of_equity is not None
                else cost_of_equity
            ),
            horizon_years=(
                overrides.horizon_years
                if overrides.horizon_years is not None
                else cfg.default_horizon_years
            ),
            exit_ev_ebitda=overrides.exit_ev_ebitda,
        )

    # -- relative valuation (needs peer data, so it lives at this layer) --

    def _relative(
        self,
        company: Company,
        history: FinancialHistory,
        inputs: ValuationInputs,
    ) -> Result[ValuationOutcome, AnalysisError]:
        latest = history.statements[0]
        market_cap = amount_of(company.market_cap)
        own = compute_multiples(MultipleInputs(
            price=inputs.price,
            market_cap=market_cap,
            net_debt=inputs.net_debt,
            eps_diluted=inputs.eps,
            book_value_per_share=inputs.book_value_per_share,
            revenue=amount_of(latest.income.revenue),
            ebitda=inputs.base_ebitda,
            ebit=amount_of(latest.income.operating_income),
            fcf=inputs.base_fcff,
            dividends_per_share=inputs.dividends_per_share,
            growth=inputs.growth,
        ))

        peers_result = self._fundamentals.get_peers(company.ticker)
        peer_multiples: list[dict[str, float | None]] = []
        peer_names: list[str] = []
        if peers_result.is_ok():
            for peer in peers_result.unwrap()[:MAX_RELATIVE_PEERS]:
                pm = self._peer_multiples(peer)
                if pm is not None:
                    peer_multiples.append(pm)
                    peer_names.append(peer.symbol)
        medians = peer_median_multiples(peer_multiples)

        implied = {
            "pe_x_eps": implied_value_per_share(medians.get("pe"), inputs.eps),
            "pb_x_bvps": implied_value_per_share(
                medians.get("pb"), inputs.book_value_per_share
            ),
        }
        ev_ebitda_median = medians.get("ev_ebitda")
        if (
            ev_ebitda_median is not None
            and inputs.base_ebitda is not None and inputs.base_ebitda > 0
            and inputs.net_debt is not None
            and inputs.shares_diluted is not None and inputs.shares_diluted > 0
        ):
            implied_ev = ev_ebitda_median * inputs.base_ebitda
            implied["ev_ebitda"] = (implied_ev - inputs.net_debt) / inputs.shares_diluted
        else:
            implied["ev_ebitda"] = None

        implied_values = [v for v in implied.values() if v is not None and v > 0]
        if not implied_values:
            return Err(InsufficientHistory(
                f"relative valuation for {company.ticker}: no peer multiples could "
                "be computed (peer set empty or peer data missing)"
            ))
        fair = sum(implied_values) / len(implied_values)

        return Ok(ValuationOutcome(
            model="relative",
            fair_value_per_share=fair,
            price=inputs.price,
            margin_of_safety=margin_of_safety(inputs.price, fair),
            assumptions={
                "peers": peer_names,
                "implied_from": {k: v for k, v in implied.items() if v is not None},
            },
            details={
                "own_multiples": own,
                "peer_median_multiples": medians,
            },
        ))

    def _peer_multiples(self, peer: Ticker) -> dict[str, float | None] | None:
        """One peer's multiples from its profile + latest annual statements.
        A failing peer is skipped (partial failure never sinks the run)."""
        company_result = self._fundamentals.get_company(peer)
        if company_result.is_err():
            return None
        peer_company = company_result.unwrap()
        history_result = self._fundamentals.get_history(peer, PeriodType.ANNUAL, 2)
        if history_result.is_err() or len(history_result.unwrap()) == 0:
            return None
        latest = history_result.unwrap().statements[0]
        rows = derive.ratio_rows(latest, None)
        return compute_multiples(MultipleInputs(
            price=amount_of(peer_company.price),
            market_cap=amount_of(peer_company.market_cap),
            net_debt=derive.net_debt_of(latest),
            eps_diluted=latest.income.eps_diluted,
            book_value_per_share=rows["book_value_per_share"],
            revenue=amount_of(latest.income.revenue),
            ebitda=amount_of(latest.income.ebitda),
            ebit=amount_of(latest.income.operating_income),
            fcf=derive.fcff_of(latest),
            dividends_per_share=rows["dividends_per_share"],
        ))
