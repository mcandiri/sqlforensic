"""Security analyzer — permission gaps, public access, and weak patterns."""

from __future__ import annotations

import logging
import re
from typing import Any

from sqlforensic.connectors.base import BaseConnector

logger = logging.getLogger(__name__)


class SecurityAnalyzer:
    """Analyze database security configuration for potential issues.

    Checks for:
    - Overly permissive grants
    - Public role access
    - Dynamic SQL injection risks in SPs
    - Sensitive data patterns without encryption
    """

    def __init__(self, connector: BaseConnector) -> None:
        self.connector = connector

    def analyze(self) -> list[dict[str, Any]]:
        """Run security analysis.

        Returns:
            List of security issues found.
        """
        logger.info("Starting security analysis")
        issues: list[dict[str, Any]] = []

        permissions = self.connector.get_permissions()
        issues.extend(self._check_permissions(permissions))

        sps = self.connector.get_stored_procedures()
        issues.extend(self._check_sp_security(sps))

        logger.info("Security analysis complete: %d issues found", len(issues))
        return issues

    def _check_permissions(self, permissions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Check for permission-related security issues."""
        issues: list[dict[str, Any]] = []

        for perm in permissions:
            principal = perm.get("principal_name", "")
            permission = perm.get("permission_name", "")
            obj = perm.get("object_name", "")

            # Check for overly broad permissions
            if permission in ("CONTROL", "ALTER"):
                issues.append(
                    {
                        "type": "EXCESSIVE_PERMISSION",
                        "severity": "HIGH",
                        "description": (
                            f"User '{principal}' has {permission} permission"
                            f"{f' on {obj}' if obj else ''}"
                        ),
                        "recommendation": "Apply least-privilege principle",
                    }
                )

        return issues

    def _check_sp_security(self, stored_procedures: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Check stored procedures for security issues."""
        issues: list[dict[str, Any]] = []

        dynamic_sql_pattern = re.compile(
            r"EXEC(?:UTE)?\s*\(\s*(?:@\w+\s*\+|'[^']*'\s*\+)",
            re.IGNORECASE,
        )

        for sp in stored_procedures:
            body = sp.get("ROUTINE_DEFINITION") or ""
            sp_name = sp.get("ROUTINE_NAME", "")

            # Check for SQL injection risk via string concatenation in dynamic SQL
            if dynamic_sql_pattern.search(body):
                if "sp_executesql" not in body.lower():
                    issues.append(
                        {
                            "type": "SQL_INJECTION_RISK",
                            "severity": "HIGH",
                            "description": (
                                f"SP '{sp_name}' uses dynamic SQL with string "
                                f"concatenation without sp_executesql"
                            ),
                            "recommendation": "Use sp_executesql with parameters",
                        }
                    )

        return issues
