"""Configuration: environment + optional TOML file, validated at startup.

- ``FMP_API_KEY`` comes from the environment only — never from a file
  that might get committed, never logged.
- Analyst defaults (risk-free rate, ERP, tax rate, horizon) live in
  ``~/.config/feat/config.toml`` or a ``--config`` path.
- Everything is validated here, before any API call; an invalid ERP is
  caught at startup, not mid-valuation.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path

from feat.domain.errors import ConfigError, Err, Ok, Result

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "feat" / "config.toml"
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "feat"


@dataclass(frozen=True, slots=True)
class FeatConfig:
    api_key: str
    risk_free_rate: float = 0.042
    equity_risk_premium: float = 0.05
    default_tax_rate: float = 0.21
    default_terminal_growth: float = 0.025
    default_horizon_years: int = 5
    default_years_history: int = 10
    rate_limit_per_minute: int = 300
    cache_dir: Path = field(default_factory=lambda: DEFAULT_CACHE_DIR)
    output_format: str = "table"


_FLOAT_BOUNDS: dict[str, tuple[float, float]] = {
    "risk_free_rate": (0.0, 0.20),
    "equity_risk_premium": (0.0, 0.15),
    "default_tax_rate": (0.0, 0.60),
    "default_terminal_growth": (-0.02, 0.05),
}
_INT_BOUNDS: dict[str, tuple[int, int]] = {
    "default_horizon_years": (1, 20),
    "default_years_history": (1, 30),
    "rate_limit_per_minute": (1, 3000),
}


def load_config(
    config_path: Path | None = None,
    env: dict[str, str] | None = None,
    require_api_key: bool = True,
) -> Result[FeatConfig, ConfigError]:
    env = env if env is not None else dict(os.environ)

    api_key = env.get("FMP_API_KEY", "").strip()
    if require_api_key and not api_key:
        return Err(ConfigError(
            "FMP_API_KEY is not set. Get a key at "
            "https://site.financialmodelingprep.com/developer/docs and export "
            "it:  export FMP_API_KEY=your_key  (or add it to your shell "
            "profile). It is read from the environment only and never stored."
        ))

    path = config_path if config_path is not None else DEFAULT_CONFIG_PATH
    file_values: dict[str, object] = {}
    if path.exists():
        try:
            with open(path, "rb") as fh:
                file_values = tomllib.load(fh)
        except (tomllib.TOMLDecodeError, OSError) as exc:
            return Err(ConfigError(f"cannot parse config file {path}: {exc}"))
    elif config_path is not None:
        return Err(ConfigError(f"config file not found: {config_path}"))

    known = {f.name for f in fields(FeatConfig)} - {"api_key"}
    unknown = set(file_values) - known
    if unknown:
        return Err(ConfigError(
            f"unknown config keys in {path}: {', '.join(sorted(unknown))}; "
            f"valid keys: {', '.join(sorted(known))}"
        ))

    kwargs: dict[str, object] = {"api_key": api_key}
    for name, value in file_values.items():
        if name == "cache_dir":
            kwargs[name] = Path(str(value)).expanduser()
        else:
            kwargs[name] = value

    try:
        config = FeatConfig(**kwargs)  # type: ignore[arg-type]
    except TypeError as exc:
        return Err(ConfigError(f"invalid config: {exc}"))

    for name, (lo, hi) in _FLOAT_BOUNDS.items():
        value = getattr(config, name)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not lo <= value <= hi:
            return Err(ConfigError(
                f"config {name} = {value!r} is out of range [{lo}, {hi}] "
                "(rates are fractions: 0.05 means 5%)"
            ))
    for name, (lo, hi) in _INT_BOUNDS.items():
        value = getattr(config, name)
        if not isinstance(value, int) or isinstance(value, bool) or not lo <= value <= hi:
            return Err(ConfigError(f"config {name} = {value!r} must be an integer in [{lo}, {hi}]"))
    if config.output_format not in {"table", "json", "csv"}:
        return Err(ConfigError(
            f"config output_format = {config.output_format!r} must be table, json or csv"
        ))
    return Ok(config)
