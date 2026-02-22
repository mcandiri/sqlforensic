"""Output formatting helpers for SQLForensic."""

from __future__ import annotations


def format_row_count(count: int | None) -> str:
    """Format row count with human-readable suffixes.

    Args:
        count: Number of rows, or None.

    Returns:
        Formatted string like '2.4M', '150K', or '1,234'.
    """
    if count is None:
        return "N/A"
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    if count >= 1_000:
        return f"{count / 1_000:.1f}K"
    return f"{count:,}"


def format_size(kb: int | None) -> str:
    """Format size in KB to human-readable string.

    Args:
        kb: Size in kilobytes, or None.

    Returns:
        Formatted string like '2.4 GB', '150 MB', or '1,234 KB'.
    """
    if kb is None:
        return "N/A"
    if kb >= 1_048_576:
        return f"{kb / 1_048_576:.1f} GB"
    if kb >= 1_024:
        return f"{kb / 1_024:.1f} MB"
    return f"{kb:,} KB"


def severity_color(severity: str) -> str:
    """Return Rich color name for severity level."""
    colors = {
        "CRITICAL": "bold red",
        "HIGH": "red",
        "MEDIUM": "yellow",
        "LOW": "cyan",
        "INFO": "dim",
    }
    return colors.get(severity.upper(), "white")


def severity_emoji(severity: str) -> str:
    """Return emoji indicator for severity level."""
    emojis = {
        "CRITICAL": "\U0001f534",
        "HIGH": "\U0001f7e0",
        "MEDIUM": "\U0001f7e1",
        "LOW": "\U0001f7e2",
        "INFO": "\u2139\ufe0f",
    }
    return emojis.get(severity.upper(), "")


def risk_label(score: float) -> str:
    """Convert numeric risk score to label."""
    if score >= 80:
        return "CRITICAL"
    if score >= 60:
        return "HIGH"
    if score >= 40:
        return "MEDIUM"
    if score >= 20:
        return "LOW"
    return "MINIMAL"


def health_bar(score: int, width: int = 50) -> str:
    """Generate a text-based health bar.

    Args:
        score: Health score (0-100).
        width: Bar width in characters.

    Returns:
        String like '████████████████░░░░░░░░░░ GOOD'.
    """
    score = max(0, min(100, score))
    filled = int(score / 100 * width)
    empty = width - filled
    bar = "\u2588" * filled + "\u2591" * empty

    if score >= 80:
        label = "EXCELLENT"
    elif score >= 60:
        label = "GOOD"
    elif score >= 40:
        label = "FAIR"
    elif score >= 20:
        label = "POOR"
    else:
        label = "CRITICAL"

    return f"{bar} {label}"


def truncate(text: str, max_length: int = 80) -> str:
    """Truncate text with ellipsis if longer than max_length."""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def build_create_index_sql(
    table_name: str,
    columns: list[str],
    include_columns: list[str] | None = None,
    index_name: str | None = None,
) -> str:
    """Generate a CREATE INDEX SQL statement.

    Args:
        table_name: Target table name.
        columns: Key columns for the index.
        include_columns: Included columns (SQL Server INCLUDE clause).
        index_name: Optional custom index name.

    Returns:
        CREATE INDEX statement string.
    """
    if not index_name:
        col_suffix = "_".join(columns)[:40]
        index_name = f"IX_{table_name}_{col_suffix}"

    col_list = ", ".join(columns)
    sql = f"CREATE INDEX [{index_name}] ON [{table_name}] ({col_list})"

    if include_columns:
        inc_list = ", ".join(include_columns)
        sql += f" INCLUDE ({inc_list})"

    return sql + ";"


def build_drop_index_sql(table_name: str, index_name: str) -> str:
    """Generate a DROP INDEX SQL statement."""
    return f"DROP INDEX [{index_name}] ON [{table_name}];"
