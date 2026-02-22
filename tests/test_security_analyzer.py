"""Tests for SecurityAnalyzer."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from sqlforensic.analyzers.security_analyzer import SecurityAnalyzer


@pytest.fixture
def analyzer_with_issues() -> SecurityAnalyzer:
    """Analyzer with mock data that triggers security issues."""
    connector = MagicMock()
    connector.get_permissions.return_value = [
        {
            "principal_name": "admin_role",
            "principal_type": "DATABASE_ROLE",
            "permission_name": "CONTROL",
            "permission_state": "GRANT",
            "object_name": None,
            "class_desc": "DATABASE",
        },
        {
            "principal_name": "app_user",
            "principal_type": "SQL_USER",
            "permission_name": "SELECT",
            "permission_state": "GRANT",
            "object_name": "Students",
            "class_desc": "OBJECT_OR_COLUMN",
        },
        {
            "principal_name": "dev_user",
            "principal_type": "SQL_USER",
            "permission_name": "ALTER",
            "permission_state": "GRANT",
            "object_name": "dbo.Users",
            "class_desc": "OBJECT_OR_COLUMN",
        },
    ]
    connector.get_stored_procedures.return_value = [
        {
            "ROUTINE_SCHEMA": "dbo",
            "ROUTINE_NAME": "sp_UnsafeSearch",
            "ROUTINE_DEFINITION": """
CREATE PROCEDURE sp_UnsafeSearch @Term VARCHAR(100)
AS BEGIN
    DECLARE @sql NVARCHAR(MAX)
    SET @sql = 'SELECT * FROM Users WHERE Name = ' + @Term
    EXEC (@sql + ' ORDER BY Id')
END""",
        },
        {
            "ROUTINE_SCHEMA": "dbo",
            "ROUTINE_NAME": "sp_SafeSearch",
            "ROUTINE_DEFINITION": """
CREATE PROCEDURE sp_SafeSearch @Term VARCHAR(100)
AS BEGIN
    DECLARE @sql NVARCHAR(MAX) = N'SELECT * FROM Users WHERE Name LIKE @p'
    EXEC sp_executesql @sql, N'@p VARCHAR(100)', @p = @Term
END""",
        },
    ]
    return SecurityAnalyzer(connector)


@pytest.fixture
def analyzer_clean() -> SecurityAnalyzer:
    """Analyzer with no security issues."""
    connector = MagicMock()
    connector.get_permissions.return_value = [
        {
            "principal_name": "app_user",
            "principal_type": "SQL_USER",
            "permission_name": "SELECT",
            "permission_state": "GRANT",
            "object_name": "Students",
            "class_desc": "OBJECT_OR_COLUMN",
        },
    ]
    connector.get_stored_procedures.return_value = [
        {
            "ROUTINE_SCHEMA": "dbo",
            "ROUTINE_NAME": "sp_Safe",
            "ROUTINE_DEFINITION": "CREATE PROCEDURE sp_Safe AS BEGIN SELECT 1 END",
        },
    ]
    return SecurityAnalyzer(connector)


class TestSecurityAnalyzer:
    def test_detects_excessive_control_permission(
        self, analyzer_with_issues: SecurityAnalyzer
    ) -> None:
        issues = analyzer_with_issues.analyze()
        control_issues = [i for i in issues if "CONTROL" in i.get("description", "")]
        assert len(control_issues) >= 1

    def test_detects_alter_permission(self, analyzer_with_issues: SecurityAnalyzer) -> None:
        issues = analyzer_with_issues.analyze()
        alter_issues = [i for i in issues if "ALTER" in i.get("description", "")]
        assert len(alter_issues) >= 1

    def test_detects_sql_injection_risk(self, analyzer_with_issues: SecurityAnalyzer) -> None:
        issues = analyzer_with_issues.analyze()
        injection_issues = [i for i in issues if i.get("type") == "SQL_INJECTION_RISK"]
        assert len(injection_issues) >= 1
        assert "sp_UnsafeSearch" in injection_issues[0]["description"]

    def test_safe_sp_not_flagged(self, analyzer_with_issues: SecurityAnalyzer) -> None:
        issues = analyzer_with_issues.analyze()
        safe_issues = [i for i in issues if "sp_SafeSearch" in i.get("description", "")]
        assert len(safe_issues) == 0

    def test_clean_database_no_issues(self, analyzer_clean: SecurityAnalyzer) -> None:
        issues = analyzer_clean.analyze()
        assert len(issues) == 0

    def test_select_permission_not_flagged(self, analyzer_with_issues: SecurityAnalyzer) -> None:
        issues = analyzer_with_issues.analyze()
        excessive = [i for i in issues if i.get("type") == "EXCESSIVE_PERMISSION"]
        descs = " ".join(i["description"] for i in excessive)
        assert "SELECT" not in descs

    def test_issues_have_required_fields(self, analyzer_with_issues: SecurityAnalyzer) -> None:
        issues = analyzer_with_issues.analyze()
        for issue in issues:
            assert "type" in issue
            assert "severity" in issue
            assert "description" in issue
            assert "recommendation" in issue
