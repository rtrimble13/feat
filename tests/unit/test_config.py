"""Config loading: fail fast, validate at startup, actionable messages."""

from feat.domain.errors import ConfigError
from feat.infra.config import load_config


class TestApiKey:
    def test_missing_key_is_actionable(self):
        result = load_config(env={})
        assert result.is_err()
        assert isinstance(result.error, ConfigError)
        assert "export FMP_API_KEY" in result.error.message
        assert result.error.exit_code == 7

    def test_offline_mode_does_not_require_key(self):
        result = load_config(env={}, require_api_key=False)
        assert result.is_ok()

    def test_key_loaded_from_env_only(self):
        result = load_config(env={"FMP_API_KEY": "sk-test"})
        assert result.unwrap().api_key == "sk-test"


class TestConfigFile:
    def test_explicit_missing_file_is_an_error(self, tmp_path):
        result = load_config(config_path=tmp_path / "nope.toml",
                             env={"FMP_API_KEY": "k"})
        assert result.is_err()
        assert "not found" in result.error.message

    def test_valid_file_overrides_defaults(self, tmp_path):
        path = tmp_path / "config.toml"
        path.write_text('equity_risk_premium = 0.055\ndefault_horizon_years = 7\n')
        config = load_config(config_path=path, env={"FMP_API_KEY": "k"}).unwrap()
        assert config.equity_risk_premium == 0.055
        assert config.default_horizon_years == 7

    def test_unknown_key_rejected_with_valid_choices(self, tmp_path):
        path = tmp_path / "config.toml"
        path.write_text('equity_risk_premum = 0.05\n')  # typo
        result = load_config(config_path=path, env={"FMP_API_KEY": "k"})
        assert result.is_err()
        assert "equity_risk_premum" in result.error.message
        assert "equity_risk_premium" in result.error.message

    def test_out_of_range_erp_caught_at_startup(self, tmp_path):
        path = tmp_path / "config.toml"
        path.write_text('equity_risk_premium = 5.0\n')  # 500% — meant 0.05
        result = load_config(config_path=path, env={"FMP_API_KEY": "k"})
        assert result.is_err()
        assert "fraction" in result.error.message

    def test_malformed_toml_rejected(self, tmp_path):
        path = tmp_path / "config.toml"
        path.write_text("this is not toml ===")
        result = load_config(config_path=path, env={"FMP_API_KEY": "k"})
        assert result.is_err()

    def test_bad_output_format_rejected(self, tmp_path):
        path = tmp_path / "config.toml"
        path.write_text('output_format = "xml"\n')
        result = load_config(config_path=path, env={"FMP_API_KEY": "k"})
        assert result.is_err()
