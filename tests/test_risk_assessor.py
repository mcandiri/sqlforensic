"""Tests for risk_assessor.py — risk assessment for schema changes."""

from __future__ import annotations

from sqlforensic.diff.diff_result import (
    ColumnInfo,
    ColumnModification,
    DiffResult,
    ForeignKeyInfo,
    RiskAssessment,
    TableDiff,
    TableInfo,
    TableModification,
)
from sqlforensic.diff.risk_assessor import RiskAssessor, calculate_overall_risk

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

STORED_PROCEDURES = [
    {
        "ROUTINE_SCHEMA": "dbo",
        "ROUTINE_NAME": "sp_GetStudents",
        "ROUTINE_DEFINITION": "SELECT * FROM Students WHERE Id = @Id",
    },
    {
        "ROUTINE_SCHEMA": "dbo",
        "ROUTINE_NAME": "sp_EnrollStudent",
        "ROUTINE_DEFINITION": (
            "INSERT INTO Enrollments (StudentId) SELECT Id FROM Students WHERE Active = 1"
        ),
    },
    {
        "ROUTINE_SCHEMA": "dbo",
        "ROUTINE_NAME": "sp_ReportCards",
        "ROUTINE_DEFINITION": (
            "SELECT s.FirstName, g.Grade FROM Students s JOIN Grades g ON s.Id = g.StudentId"
        ),
    },
    {
        "ROUTINE_SCHEMA": "dbo",
        "ROUTINE_NAME": "sp_CallerOfGetStudents",
        "ROUTINE_DEFINITION": "EXEC sp_GetStudents @Id = 1",
    },
]

VIEWS = [
    {
        "TABLE_SCHEMA": "dbo",
        "TABLE_NAME": "vw_StudentList",
        "VIEW_DEFINITION": "SELECT Id, FirstName FROM Students",
    },
]

FOREIGN_KEYS: list[dict] = []


def _make_assessor(
    sps: list[dict] | None = None,
    fks: list[dict] | None = None,
    views: list[dict] | None = None,
) -> RiskAssessor:
    return RiskAssessor(
        stored_procedures=sps if sps is not None else STORED_PROCEDURES,
        foreign_keys=fks if fks is not None else FOREIGN_KEYS,
        views=views if views is not None else VIEWS,
    )


def _empty_diff(**overrides) -> DiffResult:
    defaults = dict(
        source_database="SrcDB",
        target_database="TgtDB",
        source_server="srv1",
        target_server="srv2",
        provider="sqlserver",
    )
    defaults.update(overrides)
    return DiffResult(**defaults)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRiskAssessor:
    """Tests for the RiskAssessor.assess() method."""

    def test_added_table_no_risk(self) -> None:
        """Adding a brand-new table should carry risk_score=0.0 and risk_level='NONE'."""
        diff = _empty_diff(
            tables=TableDiff(
                added_tables=[TableInfo(schema="dbo", name="NewTable", columns=[], row_count=0)],
            ),
        )
        assessor = _make_assessor()
        risks = assessor.assess(diff)

        add_risks = [r for r in risks if "ADD TABLE" in r.change_description]
        assert len(add_risks) == 1
        assert add_risks[0].risk_score == 0.0
        assert add_risks[0].risk_level == "NONE"

    def test_removed_table_with_dependents(self) -> None:
        """Removing a table referenced by 3 SPs should produce a high risk score."""
        # "Students" is referenced in sp_GetStudents, sp_EnrollStudent, sp_ReportCards
        diff = _empty_diff(
            tables=TableDiff(
                removed_tables=[
                    TableInfo(schema="dbo", name="Students", columns=[], row_count=15000),
                ],
            ),
        )
        assessor = _make_assessor()
        risks = assessor.assess(diff)

        drop_risks = [r for r in risks if "DROP TABLE" in r.change_description]
        assert len(drop_risks) == 1
        risk = drop_risks[0]

        # 3 SPs + 1 view reference Students => 4 dependents
        # score = 0.5 + 0.15 * 4 = 1.1 => capped at 1.0
        assert risk.risk_score >= 0.5
        assert risk.risk_level in ("HIGH", "CRITICAL")
        assert len(risk.affected_objects) >= 3

    def test_removed_column_escalates_with_dependents(self) -> None:
        """More SP dependents on a column should produce a higher risk score."""
        # "FirstName" is used in sp_ReportCards ("s.FirstName") and vw_StudentList
        diff = _empty_diff(
            tables=TableDiff(
                modified_tables=[
                    TableModification(
                        table_name="Students",
                        table_schema="dbo",
                        removed_columns=[
                            ColumnInfo(name="FirstName", data_type="varchar", max_length=100),
                        ],
                    ),
                ],
            ),
        )
        assessor = _make_assessor()
        risks = assessor.assess(diff)

        col_risks = [
            r
            for r in risks
            if "DROP COLUMN" in r.change_description and "FirstName" in r.change_description
        ]
        assert len(col_risks) == 1
        risk = col_risks[0]
        # base = 0.3, has at least 1 dependent
        assert risk.risk_score >= 0.3
        assert len(risk.affected_objects) >= 1

    def test_nullable_column_add_low_risk(self) -> None:
        """Adding a nullable column should have risk_score=0.05."""
        diff = _empty_diff(
            tables=TableDiff(
                modified_tables=[
                    TableModification(
                        table_name="Students",
                        table_schema="dbo",
                        added_columns=[
                            ColumnInfo(
                                name="NickName",
                                data_type="varchar",
                                max_length=50,
                                is_nullable=True,
                            ),
                        ],
                    ),
                ],
            ),
        )
        assessor = _make_assessor()
        risks = assessor.assess(diff)

        add_risks = [
            r
            for r in risks
            if "ADD COLUMN" in r.change_description and "NickName" in r.change_description
        ]
        assert len(add_risks) == 1
        assert add_risks[0].risk_score == 0.05

    def test_not_null_column_add_higher_risk(self) -> None:
        """Adding a NOT NULL column should have risk_score=0.15."""
        diff = _empty_diff(
            tables=TableDiff(
                modified_tables=[
                    TableModification(
                        table_name="Students",
                        table_schema="dbo",
                        added_columns=[
                            ColumnInfo(name="RequiredField", data_type="int", is_nullable=False),
                        ],
                    ),
                ],
            ),
        )
        assessor = _make_assessor()
        risks = assessor.assess(diff)

        add_risks = [
            r
            for r in risks
            if "ADD COLUMN" in r.change_description and "RequiredField" in r.change_description
        ]
        assert len(add_risks) == 1
        assert add_risks[0].risk_score == 0.15

    def test_type_change_breaking(self) -> None:
        """A breaking type change should include dependents in affected_objects."""
        diff = _empty_diff(
            tables=TableDiff(
                modified_tables=[
                    TableModification(
                        table_name="Students",
                        table_schema="dbo",
                        modified_columns=[
                            ColumnModification(
                                column_name="Id",
                                change_type="type_change",
                                old_value="int",
                                new_value="bigint",
                                is_breaking=True,
                            ),
                        ],
                    ),
                ],
            ),
        )
        assessor = _make_assessor()
        risks = assessor.assess(diff)

        type_risks = [r for r in risks if "type_change" in r.change_description]
        assert len(type_risks) == 1
        risk = type_risks[0]
        # Breaking => affected_objects includes dependents
        assert len(risk.affected_objects) >= 1
        assert risk.risk_score > 0.2

    def test_nullability_to_not_null_breaking(self) -> None:
        """YES->NO nullability change (is_breaking=True) should be flagged."""
        diff = _empty_diff(
            tables=TableDiff(
                modified_tables=[
                    TableModification(
                        table_name="Students",
                        table_schema="dbo",
                        modified_columns=[
                            ColumnModification(
                                column_name="Email",
                                change_type="nullability_change",
                                old_value="YES",
                                new_value="NO",
                                is_breaking=True,
                            ),
                        ],
                    ),
                ],
            ),
        )
        assessor = _make_assessor()
        risks = assessor.assess(diff)

        null_risks = [r for r in risks if "nullability_change" in r.change_description]
        assert len(null_risks) == 1
        risk = null_risks[0]
        assert len(risk.breaking_changes) >= 1
        assert risk.risk_score >= 0.2

    def test_removed_fk_risk(self) -> None:
        """Removing a foreign key should carry a 0.15 risk score."""
        diff = _empty_diff(
            foreign_keys_removed=[
                ForeignKeyInfo(
                    constraint_name="FK_Orders_Customers",
                    parent_schema="dbo",
                    parent_table="Orders",
                    parent_column="CustomerId",
                    referenced_schema="dbo",
                    referenced_table="Customers",
                    referenced_column="Id",
                ),
            ],
        )
        assessor = _make_assessor()
        risks = assessor.assess(diff)

        fk_risks = [r for r in risks if "DROP FK" in r.change_description]
        assert len(fk_risks) == 1
        assert fk_risks[0].risk_score == 0.15
        assert fk_risks[0].risk_level == "LOW"

    def test_overall_risk_calculation(self) -> None:
        """calculate_overall_risk should return the level of the highest-scored risk."""
        risks = [
            RiskAssessment(risk_score=0.05, risk_level="LOW"),
            RiskAssessment(risk_score=0.45, risk_level="HIGH"),
            RiskAssessment(risk_score=0.1, risk_level="LOW"),
        ]
        assert calculate_overall_risk(risks) == "HIGH"

        # All low
        low_risks = [
            RiskAssessment(risk_score=0.05, risk_level="LOW"),
            RiskAssessment(risk_score=0.1, risk_level="LOW"),
        ]
        assert calculate_overall_risk(low_risks) == "LOW"

        # Critical
        critical_risks = [
            RiskAssessment(risk_score=0.9, risk_level="CRITICAL"),
        ]
        assert calculate_overall_risk(critical_risks) == "CRITICAL"

        # Empty
        assert calculate_overall_risk([]) == "NONE"

    def test_removed_sp_with_callers(self) -> None:
        """Removing an SP that is called by another SP should increase risk."""
        diff = _empty_diff()
        # sp_GetStudents is called by sp_CallerOfGetStudents
        diff.procedures.removed = [
            {"schema": "dbo", "name": "sp_GetStudents"},
        ]

        assessor = _make_assessor()
        risks = assessor.assess(diff)

        sp_risks = [r for r in risks if "DROP PROCEDURE" in r.change_description]
        assert len(sp_risks) == 1
        risk = sp_risks[0]
        # base 0.1 + 0.1 * callers (at least 1)
        assert risk.risk_score >= 0.2
        assert len(risk.affected_objects) >= 1
        assert any("sp_CallerOfGetStudents" in obj for obj in risk.affected_objects)

    def test_empty_diff_no_risks(self) -> None:
        """An empty diff should produce an empty list of risks."""
        diff = _empty_diff()
        assessor = _make_assessor()
        risks = assessor.assess(diff)
        assert risks == []
