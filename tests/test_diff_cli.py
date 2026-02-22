"""Tests for the CLI diff command using Click's CliRunner."""

from __future__ import annotations

from click.testing import CliRunner

from sqlforensic.cli import main


class TestDiffCLI:
    """Tests for the 'sqlforensic diff' CLI sub-command."""

    def test_diff_help(self) -> None:
        """'sqlforensic diff --help' should display help text with key option names."""
        runner = CliRunner()
        result = runner.invoke(main, ["diff", "--help"])

        assert result.exit_code == 0
        assert "source-database" in result.output
        assert "target-database" in result.output

    def test_diff_missing_databases(self) -> None:
        """Omitting required --source-database/--target-database should fail."""
        runner = CliRunner()
        result = runner.invoke(main, ["diff"])

        # Click should report a missing required option and exit non-zero
        assert result.exit_code != 0

    def test_diff_output_format_choices(self) -> None:
        """The --format option should accept valid choices and reject bad ones."""
        runner = CliRunner()

        # Verify invalid format is rejected
        result = runner.invoke(
            main,
            [
                "diff",
                "--source-database",
                "SrcDB",
                "--target-database",
                "TgtDB",
                "--format",
                "invalid_format",
            ],
        )
        assert result.exit_code != 0

        # Verify valid formats appear in the help text
        help_result = runner.invoke(main, ["diff", "--help"])
        assert "console" in help_result.output
        assert "json" in help_result.output
