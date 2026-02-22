"""Tests for CLI commands using Click testing utilities."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from sqlforensic import AnalysisReport
from sqlforensic.cli import main


class TestCLI:
    """Tests for the sqlforensic CLI commands."""

    def test_main_group_shows_help(self) -> None:
        """Running 'sqlforensic --help' should show the help text and exit 0."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])

        assert result.exit_code == 0
        assert "SQLForensic" in result.output
        assert "Database forensics" in result.output

    def test_version_flag(self) -> None:
        """Running 'sqlforensic --version' should display the version."""
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])

        assert result.exit_code == 0
        assert "sqlforensic" in result.output

    def test_scan_requires_database(self) -> None:
        """The scan command without --database should fail validation."""
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "scan",
                "--server",
                "localhost",
                "--user",
                "sa",
                "--password",
                "test",
            ],
        )

        # Should either fail with error message or exit non-zero
        # because database is not provided and validate() returns error
        assert result.exit_code != 0 or "Error" in result.output or "Database" in result.output

    def test_scan_command_with_mock(self, sample_report: AnalysisReport) -> None:
        """scan command should succeed when DatabaseForensic.analyze is mocked."""
        runner = CliRunner()

        with patch("sqlforensic.cli._build_forensic") as mock_build:
            mock_forensic = MagicMock()
            mock_forensic.analyze.return_value = sample_report
            mock_build.return_value = mock_forensic

            result = runner.invoke(
                main,
                [
                    "scan",
                    "--database",
                    "SchoolDB",
                    "--user",
                    "sa",
                    "--password",
                    "test",
                ],
            )

            assert result.exit_code == 0
            assert (
                "SchoolDB" in result.output
                or "Health" in result.output.upper()
                or "HEALTH" in result.output
            )

    def test_health_command_with_mock(self, sample_report: AnalysisReport) -> None:
        """health command should display health score from mocked analysis."""
        runner = CliRunner()

        with patch("sqlforensic.cli._build_forensic") as mock_build:
            mock_forensic = MagicMock()
            mock_forensic.analyze.return_value = sample_report
            mock_build.return_value = mock_forensic

            result = runner.invoke(
                main,
                [
                    "health",
                    "--database",
                    "SchoolDB",
                    "--user",
                    "sa",
                    "--password",
                    "test",
                ],
            )

            assert result.exit_code == 0
            assert "HEALTH" in result.output.upper() or "SCORE" in result.output.upper()

    def test_subcommands_registered(self) -> None:
        """All expected subcommands should be registered with the main group."""
        expected_commands = {
            "scan",
            "schema",
            "relationships",
            "procedures",
            "indexes",
            "deadcode",
            "graph",
            "impact",
            "health",
        }
        registered = set(main.commands.keys())
        assert expected_commands.issubset(registered), (
            f"Missing subcommands: {expected_commands - registered}"
        )
