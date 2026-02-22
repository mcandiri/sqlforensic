"""SQL stored procedure parser — extracts table references, operations, and complexity metrics."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from sqlforensic.utils.sql_patterns import (
    CASE_PATTERN,
    CURSOR_PATTERN,
    DELETE_PATTERN,
    DYNAMIC_SQL_PATTERN,
    INSERT_PATTERN,
    JOIN_PATTERN,
    NOLOCK_PATTERN,
    SELECT_FROM_PATTERN,
    SELECT_STAR_PATTERN,
    TABLE_REF_PATTERN,
    TEMP_TABLE_PATTERN,
    UPDATE_PATTERN,
)


@dataclass
class SPParseResult:
    """Result of parsing a stored procedure body."""

    name: str = ""
    schema: str = ""
    referenced_tables: list[str] = field(default_factory=list)
    crud_operations: dict[str, list[str]] = field(default_factory=dict)
    join_count: int = 0
    subquery_depth: int = 0
    line_count: int = 0
    has_cursors: bool = False
    has_dynamic_sql: bool = False
    has_temp_tables: bool = False
    case_count: int = 0
    complexity_score: int = 0
    complexity_category: str = "Simple"
    anti_patterns: list[str] = field(default_factory=list)
    parameters: list[dict[str, str]] = field(default_factory=list)


class SPParser:
    """Parser for SQL stored procedure bodies.

    Extracts table references, CRUD operations, complexity metrics,
    and detects anti-patterns using regex-based analysis and sqlparse.
    """

    def parse(self, sp: dict[str, Any]) -> SPParseResult:
        """Parse a stored procedure and extract all metadata.

        Args:
            sp: Dict with keys ROUTINE_SCHEMA, ROUTINE_NAME, ROUTINE_DEFINITION.

        Returns:
            SPParseResult with all extracted information.
        """
        result = SPParseResult(
            name=sp.get("ROUTINE_NAME", ""),
            schema=sp.get("ROUTINE_SCHEMA", ""),
        )

        body = sp.get("ROUTINE_DEFINITION") or ""
        if not body:
            return result

        result.line_count = len(body.strip().splitlines())
        result.referenced_tables = self._extract_table_references(body)
        result.crud_operations = self._extract_crud_operations(body)
        result.join_count = len(re.findall(JOIN_PATTERN, body, re.IGNORECASE))
        result.subquery_depth = self._calculate_subquery_depth(body)
        result.has_cursors = bool(re.search(CURSOR_PATTERN, body, re.IGNORECASE))
        result.has_dynamic_sql = bool(re.search(DYNAMIC_SQL_PATTERN, body, re.IGNORECASE))
        result.has_temp_tables = bool(re.search(TEMP_TABLE_PATTERN, body, re.IGNORECASE))
        result.case_count = len(re.findall(CASE_PATTERN, body, re.IGNORECASE))
        result.anti_patterns = self._detect_anti_patterns(body)
        result.parameters = self._extract_parameters(body)
        result.complexity_score = self._calculate_complexity(result)
        result.complexity_category = self._categorize_complexity(result.complexity_score)

        return result

    def _extract_table_references(self, body: str) -> list[str]:
        """Extract all table names referenced in the SP body."""
        tables: set[str] = set()

        for match in re.finditer(TABLE_REF_PATTERN, body, re.IGNORECASE):
            table = match.group(2).strip().strip('[]"')
            if not self._is_sql_keyword(table):
                tables.add(table)

        for match in re.finditer(JOIN_PATTERN, body, re.IGNORECASE):
            table = match.group(2).strip().strip('[]"')
            if not self._is_sql_keyword(table):
                tables.add(table)

        for match in re.finditer(SELECT_FROM_PATTERN, body, re.IGNORECASE):
            table = match.group(1).strip().strip('[]"')
            if not self._is_sql_keyword(table):
                tables.add(table)

        # Remove temp tables and common false positives
        tables = {t for t in tables if not t.startswith(("#", "@", "temp", "tmp"))}
        return sorted(tables)

    def _extract_crud_operations(self, body: str) -> dict[str, list[str]]:
        """Extract CRUD operations and their target tables."""
        ops: dict[str, list[str]] = {
            "SELECT": [],
            "INSERT": [],
            "UPDATE": [],
            "DELETE": [],
        }

        for match in re.finditer(SELECT_FROM_PATTERN, body, re.IGNORECASE):
            table = match.group(1).strip().strip('[]"')
            if not self._is_sql_keyword(table) and table not in ops["SELECT"]:
                ops["SELECT"].append(table)

        for match in re.finditer(INSERT_PATTERN, body, re.IGNORECASE):
            table = match.group(1).strip().strip('[]"')
            if not self._is_sql_keyword(table) and table not in ops["INSERT"]:
                ops["INSERT"].append(table)

        for match in re.finditer(UPDATE_PATTERN, body, re.IGNORECASE):
            table = match.group(1).strip().strip('[]"')
            if not self._is_sql_keyword(table) and table not in ops["UPDATE"]:
                ops["UPDATE"].append(table)

        for match in re.finditer(DELETE_PATTERN, body, re.IGNORECASE):
            table = match.group(1).strip().strip('[]"')
            if not self._is_sql_keyword(table) and table not in ops["DELETE"]:
                ops["DELETE"].append(table)

        return ops

    def _calculate_subquery_depth(self, body: str) -> int:
        """Calculate maximum nesting depth of subqueries."""
        max_depth = 0
        current_depth = 0
        upper = body.upper()
        i = 0
        while i < len(upper):
            if upper[i] == "(":
                # Skip whitespace after opening paren to find SELECT
                j = i + 1
                while j < len(upper) and upper[j] in " \t\r\n":
                    j += 1
                if upper[j : j + 6] == "SELECT":
                    current_depth += 1
                    max_depth = max(max_depth, current_depth)
            elif upper[i] == ")":
                if current_depth > 0:
                    current_depth -= 1
            i += 1
        return max_depth

    def _detect_anti_patterns(self, body: str) -> list[str]:
        """Detect SQL anti-patterns in the procedure body."""
        patterns: list[str] = []

        if re.search(SELECT_STAR_PATTERN, body, re.IGNORECASE):
            patterns.append("SELECT * usage — specify columns explicitly")

        if re.search(NOLOCK_PATTERN, body, re.IGNORECASE):
            patterns.append("NOLOCK hint — may cause dirty reads")

        if re.search(CURSOR_PATTERN, body, re.IGNORECASE):
            patterns.append("Cursor usage — consider set-based operations")

        if re.search(DYNAMIC_SQL_PATTERN, body, re.IGNORECASE):
            if "sp_executesql" not in body.lower():
                patterns.append(
                    "Dynamic SQL with string concatenation — use sp_executesql with parameters"
                )

        return patterns

    def _extract_parameters(self, body: str) -> list[dict[str, str]]:
        """Extract input/output parameters from the SP definition."""
        params: list[dict[str, str]] = []
        param_pattern = re.compile(
            r"@(\w+)\s+([\w\(\),\s]+?)(?:\s*=\s*[^,\n]+)?(?:\s+OUTPUT|\s+OUT)?\s*(?:,|AS\b|\))",
            re.IGNORECASE,
        )

        # Look in CREATE PROCEDURE header
        header_match = re.search(
            r"CREATE\s+(?:OR\s+ALTER\s+)?PROC(?:EDURE)?\s+[\w.\[\]]+\s*\((.*?)\)\s*AS",
            body,
            re.IGNORECASE | re.DOTALL,
        )
        if not header_match:
            header_match = re.search(
                r"CREATE\s+(?:OR\s+ALTER\s+)?PROC(?:EDURE)?\s+[\w.\[\]]+\s+(.*?)\s+AS\b",
                body,
                re.IGNORECASE | re.DOTALL,
            )

        if header_match:
            header = header_match.group(1)
            for match in param_pattern.finditer(header):
                direction = "OUTPUT" if "output" in match.group(0).lower() else "INPUT"
                params.append(
                    {
                        "name": f"@{match.group(1)}",
                        "type": match.group(2).strip(),
                        "direction": direction,
                    }
                )

        return params

    def _calculate_complexity(self, result: SPParseResult) -> int:
        """Calculate complexity score based on various factors."""
        score = 0

        # Line count contribution
        if result.line_count > 200:
            score += 20
        elif result.line_count > 100:
            score += 10
        elif result.line_count > 50:
            score += 5

        # Joins
        score += min(result.join_count * 3, 30)

        # Subquery depth
        score += result.subquery_depth * 5

        # Cursors are a significant complexity indicator
        if result.has_cursors:
            score += 15

        # Dynamic SQL
        if result.has_dynamic_sql:
            score += 10

        # Temp tables
        if result.has_temp_tables:
            score += 5

        # CASE statements
        score += min(result.case_count * 2, 10)

        # Table references
        table_count = len(result.referenced_tables)
        if table_count > 10:
            score += 15
        elif table_count > 5:
            score += 8

        return score

    def _categorize_complexity(self, score: int) -> str:
        """Categorize complexity score into human-readable label."""
        if score >= 50:
            return "Complex"
        elif score >= 20:
            return "Medium"
        return "Simple"

    @staticmethod
    def _is_sql_keyword(token: str) -> bool:
        """Check if a token is a SQL keyword rather than a table name."""
        keywords = {
            "select",
            "from",
            "where",
            "insert",
            "into",
            "update",
            "delete",
            "join",
            "inner",
            "outer",
            "left",
            "right",
            "cross",
            "on",
            "and",
            "or",
            "not",
            "in",
            "exists",
            "between",
            "like",
            "is",
            "null",
            "set",
            "values",
            "as",
            "begin",
            "end",
            "if",
            "else",
            "while",
            "return",
            "declare",
            "exec",
            "execute",
            "create",
            "alter",
            "drop",
            "table",
            "procedure",
            "function",
            "view",
            "index",
            "trigger",
            "grant",
            "revoke",
            "commit",
            "rollback",
            "transaction",
            "group",
            "order",
            "by",
            "having",
            "union",
            "all",
            "distinct",
            "top",
            "limit",
            "offset",
            "fetch",
            "next",
            "rows",
            "only",
            "case",
            "when",
            "then",
            "cast",
            "convert",
            "coalesce",
        }
        return token.lower() in keywords
