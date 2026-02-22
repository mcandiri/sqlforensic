"""Tests for formatting utility functions."""

from __future__ import annotations

from sqlforensic.utils.formatting import (
    build_create_index_sql,
    build_drop_index_sql,
    format_row_count,
    format_size,
    health_bar,
    risk_label,
    severity_color,
    severity_emoji,
    truncate,
)


class TestFormatRowCount:
    def test_none_returns_na(self) -> None:
        assert format_row_count(None) == "N/A"

    def test_millions(self) -> None:
        assert format_row_count(2_400_000) == "2.4M"

    def test_thousands(self) -> None:
        assert format_row_count(150_000) == "150.0K"

    def test_small_number(self) -> None:
        assert format_row_count(42) == "42"

    def test_zero(self) -> None:
        assert format_row_count(0) == "0"

    def test_exact_million(self) -> None:
        assert format_row_count(1_000_000) == "1.0M"

    def test_exact_thousand(self) -> None:
        assert format_row_count(1_000) == "1.0K"


class TestFormatSize:
    def test_none_returns_na(self) -> None:
        assert format_size(None) == "N/A"

    def test_gigabytes(self) -> None:
        result = format_size(2_000_000)
        assert "GB" in result

    def test_megabytes(self) -> None:
        result = format_size(5_000)
        assert "MB" in result

    def test_kilobytes(self) -> None:
        result = format_size(500)
        assert "KB" in result

    def test_zero(self) -> None:
        assert format_size(0) == "0 KB"


class TestSeverityColor:
    def test_critical(self) -> None:
        assert "red" in severity_color("CRITICAL")

    def test_high(self) -> None:
        assert "red" in severity_color("HIGH")

    def test_medium(self) -> None:
        assert "yellow" in severity_color("MEDIUM")

    def test_low(self) -> None:
        assert "cyan" in severity_color("LOW")

    def test_unknown_returns_white(self) -> None:
        assert severity_color("UNKNOWN") == "white"

    def test_case_insensitive(self) -> None:
        assert severity_color("critical") == severity_color("CRITICAL")


class TestSeverityEmoji:
    def test_critical_has_emoji(self) -> None:
        assert severity_emoji("CRITICAL") != ""

    def test_unknown_returns_empty(self) -> None:
        assert severity_emoji("UNKNOWN") == ""


class TestRiskLabel:
    def test_critical(self) -> None:
        assert risk_label(80) == "CRITICAL"
        assert risk_label(100) == "CRITICAL"

    def test_high(self) -> None:
        assert risk_label(60) == "HIGH"

    def test_medium(self) -> None:
        assert risk_label(40) == "MEDIUM"

    def test_low(self) -> None:
        assert risk_label(20) == "LOW"

    def test_minimal(self) -> None:
        assert risk_label(0) == "MINIMAL"
        assert risk_label(19) == "MINIMAL"


class TestHealthBar:
    def test_excellent(self) -> None:
        result = health_bar(90)
        assert "EXCELLENT" in result

    def test_good(self) -> None:
        result = health_bar(65)
        assert "GOOD" in result

    def test_fair(self) -> None:
        result = health_bar(45)
        assert "FAIR" in result

    def test_poor(self) -> None:
        result = health_bar(25)
        assert "POOR" in result

    def test_critical_score(self) -> None:
        result = health_bar(10)
        assert "CRITICAL" in result

    def test_clamps_above_100(self) -> None:
        result = health_bar(150)
        assert "EXCELLENT" in result

    def test_clamps_below_0(self) -> None:
        result = health_bar(-50)
        assert "CRITICAL" in result

    def test_custom_width(self) -> None:
        result = health_bar(50, width=20)
        assert len(result.split()[0]) == 20


class TestTruncate:
    def test_short_text_unchanged(self) -> None:
        assert truncate("hello", 80) == "hello"

    def test_long_text_truncated(self) -> None:
        result = truncate("a" * 100, 20)
        assert len(result) == 20
        assert result.endswith("...")

    def test_exact_length_unchanged(self) -> None:
        text = "a" * 80
        assert truncate(text, 80) == text


class TestBuildCreateIndexSQL:
    def test_basic_index(self) -> None:
        sql = build_create_index_sql("Orders", ["CustomerId"])
        assert "CREATE INDEX" in sql
        assert "[Orders]" in sql
        assert "CustomerId" in sql
        assert sql.endswith(";")

    def test_composite_index(self) -> None:
        sql = build_create_index_sql("Orders", ["CustomerId", "OrderDate"])
        assert "CustomerId, OrderDate" in sql

    def test_include_columns(self) -> None:
        sql = build_create_index_sql("Orders", ["CustomerId"], include_columns=["Total"])
        assert "INCLUDE" in sql
        assert "Total" in sql

    def test_custom_name(self) -> None:
        sql = build_create_index_sql("Orders", ["CustomerId"], index_name="IX_Custom")
        assert "[IX_Custom]" in sql

    def test_auto_generated_name(self) -> None:
        sql = build_create_index_sql("Orders", ["CustomerId"])
        assert "IX_Orders_CustomerId" in sql


class TestBuildDropIndexSQL:
    def test_drop_index(self) -> None:
        sql = build_drop_index_sql("Orders", "IX_Orders_CustomerId")
        assert "DROP INDEX" in sql
        assert "[IX_Orders_CustomerId]" in sql
        assert "[Orders]" in sql
        assert sql.endswith(";")
