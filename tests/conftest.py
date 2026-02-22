"""Shared test fixtures with mock database data for a fictional SchoolDB."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from sqlforensic import AnalysisReport
from sqlforensic.config import ConnectionConfig


@pytest.fixture
def connection_config() -> ConnectionConfig:
    """Standard SQL Server connection config."""
    return ConnectionConfig(
        provider="sqlserver",
        server="localhost",
        database="SchoolDB",
        username="sa",
        password="test-password",
        port=1433,
    )


@pytest.fixture
def mock_connector(connection_config: ConnectionConfig) -> MagicMock:
    """Mock connector with SchoolDB data pre-loaded."""
    connector = MagicMock()
    connector.config = connection_config
    connector.is_connected = True

    connector.get_tables.return_value = MOCK_TABLES
    connector.get_columns.side_effect = _mock_get_columns
    connector.get_foreign_keys.return_value = MOCK_FOREIGN_KEYS
    connector.get_stored_procedures.return_value = MOCK_STORED_PROCEDURES
    connector.get_views.return_value = MOCK_VIEWS
    connector.get_functions.return_value = MOCK_FUNCTIONS
    connector.get_indexes.return_value = MOCK_INDEXES
    connector.get_missing_indexes.return_value = MOCK_MISSING_INDEXES
    connector.get_table_sizes.return_value = MOCK_TABLE_SIZES
    connector.get_permissions.return_value = MOCK_PERMISSIONS

    return connector


@pytest.fixture
def sample_tables() -> list[dict]:
    """Tables with column data embedded."""
    tables = []
    for t in MOCK_TABLES:
        schema = t["TABLE_SCHEMA"]
        name = t["TABLE_NAME"]
        cols = _mock_get_columns(schema, name)
        tables.append(
            {
                **t,
                "columns": cols,
                "column_count": len(cols),
                "has_primary_key": any(c.get("is_primary_key") for c in cols),
            }
        )
    return tables


@pytest.fixture
def sample_report(sample_tables: list[dict]) -> AnalysisReport:
    """Pre-built AnalysisReport for testing scorers and reporters."""
    return AnalysisReport(
        database="SchoolDB",
        provider="sqlserver",
        health_score=68,
        tables=sample_tables,
        views=MOCK_VIEWS,
        stored_procedures=MOCK_STORED_PROCEDURES,
        functions=MOCK_FUNCTIONS,
        relationships=MOCK_FOREIGN_KEYS,
        implicit_relationships=[
            {
                "parent_table": "Payments",
                "parent_column": "StudentId",
                "referenced_table": "Students",
                "referenced_column": "Id",
                "confidence": 60,
                "source": "naming_convention",
                "source_name": "StudentId -> Students",
            },
        ],
        indexes=MOCK_INDEXES,
        missing_indexes=MOCK_MISSING_INDEXES,
        unused_indexes=[
            {
                "table_name": "Attendance",
                "index_name": "IX_Old_Attendance",
                "index_type": "NONCLUSTERED",
                "columns": "OldColumn",
                "user_updates": 500,
                "drop_sql": "DROP INDEX [IX_Old_Attendance] ON [Attendance];",
            },
        ],
        duplicate_indexes=[
            {
                "table_name": "Enrollments",
                "index_name": "IX_Dup_Enrollments",
                "duplicate_of": "IX_Enrollments_CourseId",
                "columns": "CourseId",
                "drop_sql": "DROP INDEX [IX_Dup_Enrollments] ON [Enrollments];",
            },
        ],
        dead_procedures=[
            {"ROUTINE_SCHEMA": "dbo", "ROUTINE_NAME": "sp_OldReport"},
            {"ROUTINE_SCHEMA": "dbo", "ROUTINE_NAME": "sp_TempCleanup"},
        ],
        dead_tables=[
            {
                "TABLE_SCHEMA": "dbo",
                "TABLE_NAME": "Logs_Archive",
                "row_count": 0,
                "column_count": 5,
            },
        ],
        orphan_columns=[
            {"table_name": "Students", "column_name": "MiddleName", "data_type": "varchar"},
        ],
        empty_tables=[
            {"TABLE_SCHEMA": "dbo", "TABLE_NAME": "AuditLog", "column_count": 8},
        ],
        dependencies={
            "nodes": [
                {"id": "Students", "type": "table", "in_degree": 5, "out_degree": 0},
                {"id": "Enrollments", "type": "table", "in_degree": 3, "out_degree": 2},
                {"id": "sp_GetStudentGrades", "type": "procedure", "in_degree": 0, "out_degree": 3},
            ],
            "edges": [
                {"source": "sp_GetStudentGrades", "target": "Students", "type": "references"},
                {"source": "sp_GetStudentGrades", "target": "Enrollments", "type": "references"},
                {"source": "Enrollments", "target": "Students", "type": "foreign_key"},
            ],
            "hotspots": [
                {
                    "table": "Students",
                    "dependent_sp_count": 15,
                    "dependent_sps": [],
                    "risk_level": "CRITICAL",
                },
                {
                    "table": "Courses",
                    "dependent_sp_count": 10,
                    "dependent_sps": [],
                    "risk_level": "HIGH",
                },
            ],
        },
        circular_dependencies=[["Schedules", "Classrooms"]],
        issues=[
            {
                "description": "Tables with no primary key",
                "severity": "HIGH",
                "count": 2,
                "penalty": 10,
                "category": "schema",
            },
            {
                "description": "Missing foreign key indexes",
                "severity": "HIGH",
                "count": 5,
                "penalty": 10,
                "category": "indexes",
            },
            {
                "description": "Unused stored procedures",
                "severity": "MEDIUM",
                "count": 2,
                "penalty": 2,
                "category": "dead_code",
            },
            {
                "description": "Circular dependencies detected",
                "severity": "HIGH",
                "count": 1,
                "penalty": 10,
                "category": "dependencies",
            },
        ],
        sp_analysis=[
            {
                "name": "sp_GetStudentGrades",
                "schema": "dbo",
                "line_count": 45,
                "referenced_tables": ["Students", "Grades", "Courses"],
                "crud_operations": {
                    "SELECT": ["Students", "Grades", "Courses"],
                    "INSERT": [],
                    "UPDATE": [],
                    "DELETE": [],
                },
                "join_count": 3,
                "subquery_depth": 1,
                "has_cursors": False,
                "has_dynamic_sql": False,
                "has_temp_tables": False,
                "case_count": 2,
                "complexity_score": 22,
                "complexity_category": "Medium",
                "anti_patterns": [],
                "parameters": [{"name": "@StudentId", "type": "INT", "direction": "INPUT"}],
            },
            {
                "name": "sp_EnrollStudent",
                "schema": "dbo",
                "line_count": 120,
                "referenced_tables": ["Students", "Courses", "Enrollments", "Payments"],
                "crud_operations": {
                    "SELECT": ["Students", "Courses"],
                    "INSERT": ["Enrollments"],
                    "UPDATE": ["Payments"],
                    "DELETE": [],
                },
                "join_count": 5,
                "subquery_depth": 2,
                "has_cursors": True,
                "has_dynamic_sql": False,
                "has_temp_tables": True,
                "case_count": 4,
                "complexity_score": 58,
                "complexity_category": "Complex",
                "anti_patterns": [
                    "Cursor usage — consider set-based operations",
                    "SELECT * usage — specify columns explicitly",
                ],
                "parameters": [],
            },
        ],
        size_info=MOCK_TABLE_SIZES,
        security_issues=[
            {
                "type": "SQL_INJECTION_RISK",
                "severity": "HIGH",
                "description": "SP 'sp_DynamicSearch' uses dynamic SQL with string concatenation",
                "recommendation": "Use sp_executesql with parameters",
            },
        ],
        risk_scores={
            "tables": [
                {
                    "name": "Students",
                    "schema": "dbo",
                    "risk_score": 85,
                    "risk_level": "CRITICAL",
                    "dependent_sp_count": 15,
                    "dependent_sps": [],
                    "fk_dependency_count": 3,
                    "row_count": 15000,
                },
            ],
            "procedures": [
                {
                    "name": "sp_EnrollStudent",
                    "schema": "dbo",
                    "risk_score": 58,
                    "risk_level": "MEDIUM",
                    "complexity_score": 58,
                    "referenced_table_count": 4,
                    "caller_count": 0,
                },
            ],
        },
        schema_overview={
            "tables": 15,
            "views": 3,
            "stored_procedures": 30,
            "functions": 5,
            "indexes": 45,
            "foreign_keys": 12,
            "total_columns": 185,
            "total_rows": 125000,
        },
    )


def _mock_get_columns(table_schema: str, table_name: str) -> list[dict]:
    """Return mock columns for a given table."""
    columns_map = {
        "Students": [
            {
                "COLUMN_NAME": "Id",
                "DATA_TYPE": "int",
                "CHARACTER_MAXIMUM_LENGTH": None,
                "IS_NULLABLE": "NO",
                "COLUMN_DEFAULT": None,
                "ORDINAL_POSITION": 1,
                "is_primary_key": 1,
            },
            {
                "COLUMN_NAME": "FirstName",
                "DATA_TYPE": "varchar",
                "CHARACTER_MAXIMUM_LENGTH": 100,
                "IS_NULLABLE": "NO",
                "COLUMN_DEFAULT": None,
                "ORDINAL_POSITION": 2,
                "is_primary_key": 0,
            },
            {
                "COLUMN_NAME": "LastName",
                "DATA_TYPE": "varchar",
                "CHARACTER_MAXIMUM_LENGTH": 100,
                "IS_NULLABLE": "NO",
                "COLUMN_DEFAULT": None,
                "ORDINAL_POSITION": 3,
                "is_primary_key": 0,
            },
            {
                "COLUMN_NAME": "Email",
                "DATA_TYPE": "varchar",
                "CHARACTER_MAXIMUM_LENGTH": 255,
                "IS_NULLABLE": "YES",
                "COLUMN_DEFAULT": None,
                "ORDINAL_POSITION": 4,
                "is_primary_key": 0,
            },
            {
                "COLUMN_NAME": "EnrollmentDate",
                "DATA_TYPE": "datetime",
                "CHARACTER_MAXIMUM_LENGTH": None,
                "IS_NULLABLE": "YES",
                "COLUMN_DEFAULT": "GETDATE()",
                "ORDINAL_POSITION": 5,
                "is_primary_key": 0,
            },
            {
                "COLUMN_NAME": "DepartmentId",
                "DATA_TYPE": "int",
                "CHARACTER_MAXIMUM_LENGTH": None,
                "IS_NULLABLE": "YES",
                "COLUMN_DEFAULT": None,
                "ORDINAL_POSITION": 6,
                "is_primary_key": 0,
            },
            {
                "COLUMN_NAME": "MiddleName",
                "DATA_TYPE": "varchar",
                "CHARACTER_MAXIMUM_LENGTH": 100,
                "IS_NULLABLE": "YES",
                "COLUMN_DEFAULT": None,
                "ORDINAL_POSITION": 7,
                "is_primary_key": 0,
            },
        ],
        "Courses": [
            {
                "COLUMN_NAME": "Id",
                "DATA_TYPE": "int",
                "CHARACTER_MAXIMUM_LENGTH": None,
                "IS_NULLABLE": "NO",
                "COLUMN_DEFAULT": None,
                "ORDINAL_POSITION": 1,
                "is_primary_key": 1,
            },
            {
                "COLUMN_NAME": "CourseName",
                "DATA_TYPE": "varchar",
                "CHARACTER_MAXIMUM_LENGTH": 200,
                "IS_NULLABLE": "NO",
                "COLUMN_DEFAULT": None,
                "ORDINAL_POSITION": 2,
                "is_primary_key": 0,
            },
            {
                "COLUMN_NAME": "Credits",
                "DATA_TYPE": "int",
                "CHARACTER_MAXIMUM_LENGTH": None,
                "IS_NULLABLE": "NO",
                "COLUMN_DEFAULT": "3",
                "ORDINAL_POSITION": 3,
                "is_primary_key": 0,
            },
            {
                "COLUMN_NAME": "DepartmentId",
                "DATA_TYPE": "int",
                "CHARACTER_MAXIMUM_LENGTH": None,
                "IS_NULLABLE": "YES",
                "COLUMN_DEFAULT": None,
                "ORDINAL_POSITION": 4,
                "is_primary_key": 0,
            },
        ],
        "Enrollments": [
            {
                "COLUMN_NAME": "Id",
                "DATA_TYPE": "int",
                "CHARACTER_MAXIMUM_LENGTH": None,
                "IS_NULLABLE": "NO",
                "COLUMN_DEFAULT": None,
                "ORDINAL_POSITION": 1,
                "is_primary_key": 1,
            },
            {
                "COLUMN_NAME": "StudentId",
                "DATA_TYPE": "int",
                "CHARACTER_MAXIMUM_LENGTH": None,
                "IS_NULLABLE": "NO",
                "COLUMN_DEFAULT": None,
                "ORDINAL_POSITION": 2,
                "is_primary_key": 0,
            },
            {
                "COLUMN_NAME": "CourseId",
                "DATA_TYPE": "int",
                "CHARACTER_MAXIMUM_LENGTH": None,
                "IS_NULLABLE": "NO",
                "COLUMN_DEFAULT": None,
                "ORDINAL_POSITION": 3,
                "is_primary_key": 0,
            },
            {
                "COLUMN_NAME": "EnrollDate",
                "DATA_TYPE": "datetime",
                "CHARACTER_MAXIMUM_LENGTH": None,
                "IS_NULLABLE": "YES",
                "COLUMN_DEFAULT": None,
                "ORDINAL_POSITION": 4,
                "is_primary_key": 0,
            },
        ],
        "Grades": [
            {
                "COLUMN_NAME": "Id",
                "DATA_TYPE": "int",
                "CHARACTER_MAXIMUM_LENGTH": None,
                "IS_NULLABLE": "NO",
                "COLUMN_DEFAULT": None,
                "ORDINAL_POSITION": 1,
                "is_primary_key": 1,
            },
            {
                "COLUMN_NAME": "StudentId",
                "DATA_TYPE": "int",
                "CHARACTER_MAXIMUM_LENGTH": None,
                "IS_NULLABLE": "NO",
                "COLUMN_DEFAULT": None,
                "ORDINAL_POSITION": 2,
                "is_primary_key": 0,
            },
            {
                "COLUMN_NAME": "CourseId",
                "DATA_TYPE": "int",
                "CHARACTER_MAXIMUM_LENGTH": None,
                "IS_NULLABLE": "NO",
                "COLUMN_DEFAULT": None,
                "ORDINAL_POSITION": 3,
                "is_primary_key": 0,
            },
            {
                "COLUMN_NAME": "Grade",
                "DATA_TYPE": "decimal",
                "CHARACTER_MAXIMUM_LENGTH": None,
                "IS_NULLABLE": "YES",
                "COLUMN_DEFAULT": None,
                "ORDINAL_POSITION": 4,
                "is_primary_key": 0,
            },
        ],
        "Payments": [
            {
                "COLUMN_NAME": "Id",
                "DATA_TYPE": "int",
                "CHARACTER_MAXIMUM_LENGTH": None,
                "IS_NULLABLE": "NO",
                "COLUMN_DEFAULT": None,
                "ORDINAL_POSITION": 1,
                "is_primary_key": 1,
            },
            {
                "COLUMN_NAME": "StudentId",
                "DATA_TYPE": "int",
                "CHARACTER_MAXIMUM_LENGTH": None,
                "IS_NULLABLE": "NO",
                "COLUMN_DEFAULT": None,
                "ORDINAL_POSITION": 2,
                "is_primary_key": 0,
            },
            {
                "COLUMN_NAME": "Amount",
                "DATA_TYPE": "decimal",
                "CHARACTER_MAXIMUM_LENGTH": None,
                "IS_NULLABLE": "NO",
                "COLUMN_DEFAULT": None,
                "ORDINAL_POSITION": 3,
                "is_primary_key": 0,
            },
            {
                "COLUMN_NAME": "PaymentDate",
                "DATA_TYPE": "datetime",
                "CHARACTER_MAXIMUM_LENGTH": None,
                "IS_NULLABLE": "YES",
                "COLUMN_DEFAULT": None,
                "ORDINAL_POSITION": 4,
                "is_primary_key": 0,
            },
        ],
        "Departments": [
            {
                "COLUMN_NAME": "Id",
                "DATA_TYPE": "int",
                "CHARACTER_MAXIMUM_LENGTH": None,
                "IS_NULLABLE": "NO",
                "COLUMN_DEFAULT": None,
                "ORDINAL_POSITION": 1,
                "is_primary_key": 1,
            },
            {
                "COLUMN_NAME": "DepartmentName",
                "DATA_TYPE": "varchar",
                "CHARACTER_MAXIMUM_LENGTH": 200,
                "IS_NULLABLE": "NO",
                "COLUMN_DEFAULT": None,
                "ORDINAL_POSITION": 2,
                "is_primary_key": 0,
            },
        ],
        "AuditLog": [
            {
                "COLUMN_NAME": "Id",
                "DATA_TYPE": "int",
                "CHARACTER_MAXIMUM_LENGTH": None,
                "IS_NULLABLE": "NO",
                "COLUMN_DEFAULT": None,
                "ORDINAL_POSITION": 1,
                "is_primary_key": 0,
            },
            {
                "COLUMN_NAME": "Action",
                "DATA_TYPE": "varchar",
                "CHARACTER_MAXIMUM_LENGTH": 500,
                "IS_NULLABLE": "YES",
                "COLUMN_DEFAULT": None,
                "ORDINAL_POSITION": 2,
                "is_primary_key": 0,
            },
        ],
        "Logs_Archive": [
            {
                "COLUMN_NAME": "Id",
                "DATA_TYPE": "int",
                "CHARACTER_MAXIMUM_LENGTH": None,
                "IS_NULLABLE": "NO",
                "COLUMN_DEFAULT": None,
                "ORDINAL_POSITION": 1,
                "is_primary_key": 0,
            },
            {
                "COLUMN_NAME": "Message",
                "DATA_TYPE": "varchar",
                "CHARACTER_MAXIMUM_LENGTH": 4000,
                "IS_NULLABLE": "YES",
                "COLUMN_DEFAULT": None,
                "ORDINAL_POSITION": 2,
                "is_primary_key": 0,
            },
        ],
    }
    return columns_map.get(
        table_name,
        [
            {
                "COLUMN_NAME": "Id",
                "DATA_TYPE": "int",
                "CHARACTER_MAXIMUM_LENGTH": None,
                "IS_NULLABLE": "NO",
                "COLUMN_DEFAULT": None,
                "ORDINAL_POSITION": 1,
                "is_primary_key": 1,
            },
        ],
    )


# ── Mock Data ──────────────────────────────────────────────────────

MOCK_TABLES = [
    {"TABLE_SCHEMA": "dbo", "TABLE_NAME": "Students", "row_count": 15000},
    {"TABLE_SCHEMA": "dbo", "TABLE_NAME": "Courses", "row_count": 200},
    {"TABLE_SCHEMA": "dbo", "TABLE_NAME": "Enrollments", "row_count": 45000},
    {"TABLE_SCHEMA": "dbo", "TABLE_NAME": "Grades", "row_count": 90000},
    {"TABLE_SCHEMA": "dbo", "TABLE_NAME": "Payments", "row_count": 32000},
    {"TABLE_SCHEMA": "dbo", "TABLE_NAME": "Departments", "row_count": 12},
    {"TABLE_SCHEMA": "dbo", "TABLE_NAME": "AuditLog", "row_count": 0},
    {"TABLE_SCHEMA": "dbo", "TABLE_NAME": "Logs_Archive", "row_count": 0},
]

MOCK_FOREIGN_KEYS = [
    {
        "constraint_name": "FK_Enrollments_Students",
        "parent_schema": "dbo",
        "parent_table": "Enrollments",
        "parent_column": "StudentId",
        "referenced_schema": "dbo",
        "referenced_table": "Students",
        "referenced_column": "Id",
    },
    {
        "constraint_name": "FK_Enrollments_Courses",
        "parent_schema": "dbo",
        "parent_table": "Enrollments",
        "parent_column": "CourseId",
        "referenced_schema": "dbo",
        "referenced_table": "Courses",
        "referenced_column": "Id",
    },
    {
        "constraint_name": "FK_Grades_Students",
        "parent_schema": "dbo",
        "parent_table": "Grades",
        "parent_column": "StudentId",
        "referenced_schema": "dbo",
        "referenced_table": "Students",
        "referenced_column": "Id",
    },
    {
        "constraint_name": "FK_Grades_Courses",
        "parent_schema": "dbo",
        "parent_table": "Grades",
        "parent_column": "CourseId",
        "referenced_schema": "dbo",
        "referenced_table": "Courses",
        "referenced_column": "Id",
    },
    {
        "constraint_name": "FK_Students_Departments",
        "parent_schema": "dbo",
        "parent_table": "Students",
        "parent_column": "DepartmentId",
        "referenced_schema": "dbo",
        "referenced_table": "Departments",
        "referenced_column": "Id",
    },
]

MOCK_STORED_PROCEDURES = [
    {
        "ROUTINE_SCHEMA": "dbo",
        "ROUTINE_NAME": "sp_GetStudentGrades",
        "ROUTINE_DEFINITION": """
CREATE PROCEDURE [dbo].[sp_GetStudentGrades]
    @StudentId INT
AS
BEGIN
    SELECT s.FirstName, s.LastName, c.CourseName, g.Grade
    FROM Students s
    INNER JOIN Enrollments e ON s.Id = e.StudentId
    INNER JOIN Courses c ON e.CourseId = c.Id
    LEFT JOIN Grades g ON g.StudentId = s.Id AND g.CourseId = c.Id
    WHERE s.Id = @StudentId
    ORDER BY c.CourseName
END
""",
        "CREATED": "2024-01-15",
        "LAST_ALTERED": "2024-06-20",
    },
    {
        "ROUTINE_SCHEMA": "dbo",
        "ROUTINE_NAME": "sp_EnrollStudent",
        "ROUTINE_DEFINITION": """
CREATE PROCEDURE [dbo].[sp_EnrollStudent]
    @StudentId INT,
    @CourseId INT
AS
BEGIN
    DECLARE @exists INT
    SELECT @exists = COUNT(*) FROM Enrollments WHERE StudentId = @StudentId AND CourseId = @CourseId

    IF @exists = 0
    BEGIN
        INSERT INTO Enrollments (StudentId, CourseId, EnrollDate)
        VALUES (@StudentId, @CourseId, GETDATE())

        -- Update payment record
        DECLARE student_cursor CURSOR FOR
        SELECT * FROM Payments WHERE StudentId = @StudentId

        OPEN student_cursor
        FETCH NEXT FROM student_cursor
        -- ... cursor processing
        CLOSE student_cursor
        DEALLOCATE student_cursor

        SELECT * FROM Students WHERE Id = @StudentId

        CREATE TABLE #TempEnrollments (Id INT, Name VARCHAR(100))
        INSERT INTO #TempEnrollments SELECT Id, FirstName FROM Students

        CASE WHEN 1=1 THEN 'Y' ELSE 'N' END
        CASE WHEN 2=2 THEN 'A' ELSE 'B' END
        CASE WHEN 3=3 THEN 'X' ELSE 'Z' END
        CASE WHEN 4=4 THEN 'P' ELSE 'Q' END
    END
END
""",
        "CREATED": "2024-02-01",
        "LAST_ALTERED": "2024-08-15",
    },
    {
        "ROUTINE_SCHEMA": "dbo",
        "ROUTINE_NAME": "sp_OldReport",
        "ROUTINE_DEFINITION": """
CREATE PROCEDURE [dbo].[sp_OldReport]
AS
BEGIN
    SELECT 1
END
""",
        "CREATED": "2022-01-01",
        "LAST_ALTERED": "2022-01-01",
    },
    {
        "ROUTINE_SCHEMA": "dbo",
        "ROUTINE_NAME": "sp_TempCleanup",
        "ROUTINE_DEFINITION": """
CREATE PROCEDURE [dbo].[sp_TempCleanup]
AS
BEGIN
    DELETE FROM AuditLog WHERE 1=0
END
""",
        "CREATED": "2023-06-01",
        "LAST_ALTERED": "2023-06-01",
    },
    {
        "ROUTINE_SCHEMA": "dbo",
        "ROUTINE_NAME": "sp_DynamicSearch",
        "ROUTINE_DEFINITION": """
CREATE PROCEDURE [dbo].[sp_DynamicSearch]
    @SearchTerm VARCHAR(100)
AS
BEGIN
    DECLARE @sql NVARCHAR(MAX)
    SET @sql = 'SELECT * FROM Students WHERE FirstName LIKE ''%' + @SearchTerm + '%'''
    EXEC(@sql)
END
""",
        "CREATED": "2024-03-01",
        "LAST_ALTERED": "2024-03-01",
    },
]

MOCK_VIEWS = [
    {
        "TABLE_SCHEMA": "dbo",
        "TABLE_NAME": "vw_StudentEnrollments",
        "VIEW_DEFINITION": (
            "SELECT s.*, e.CourseId FROM Students s JOIN Enrollments e ON s.Id = e.StudentId"
        ),
    },
    {
        "TABLE_SCHEMA": "dbo",
        "TABLE_NAME": "vw_CourseGrades",
        "VIEW_DEFINITION": (
            "SELECT c.CourseName, AVG(g.Grade) as AvgGrade"
            " FROM Courses c JOIN Grades g ON c.Id = g.CourseId"
            " GROUP BY c.CourseName"
        ),
    },
]

MOCK_FUNCTIONS = [
    {
        "ROUTINE_SCHEMA": "dbo",
        "ROUTINE_NAME": "fn_GetFullName",
        "ROUTINE_DEFINITION": (
            "CREATE FUNCTION fn_GetFullName(@StudentId INT)"
            " RETURNS VARCHAR(200) AS BEGIN RETURN"
            " (SELECT FirstName + ' ' + LastName"
            " FROM Students WHERE Id = @StudentId) END"
        ),
        "DATA_TYPE": "varchar",
        "CREATED": "2024-01-01",
        "LAST_ALTERED": "2024-01-01",
    },
]

MOCK_INDEXES = [
    {
        "table_schema": "dbo",
        "table_name": "Students",
        "index_name": "PK_Students",
        "index_type": "CLUSTERED",
        "is_unique": True,
        "is_primary_key": True,
        "columns": "Id",
        "user_seeks": 50000,
        "user_scans": 1200,
        "user_lookups": 3000,
        "user_updates": 800,
    },
    {
        "table_schema": "dbo",
        "table_name": "Enrollments",
        "index_name": "PK_Enrollments",
        "index_type": "CLUSTERED",
        "is_unique": True,
        "is_primary_key": True,
        "columns": "Id",
        "user_seeks": 30000,
        "user_scans": 500,
        "user_lookups": 1000,
        "user_updates": 2000,
    },
    {
        "table_schema": "dbo",
        "table_name": "Enrollments",
        "index_name": "IX_Enrollments_StudentId",
        "index_type": "NONCLUSTERED",
        "is_unique": False,
        "is_primary_key": False,
        "columns": "StudentId",
        "user_seeks": 25000,
        "user_scans": 100,
        "user_lookups": 0,
        "user_updates": 2000,
    },
    {
        "table_schema": "dbo",
        "table_name": "Enrollments",
        "index_name": "IX_Enrollments_CourseId",
        "index_type": "NONCLUSTERED",
        "is_unique": False,
        "is_primary_key": False,
        "columns": "CourseId",
        "user_seeks": 15000,
        "user_scans": 200,
        "user_lookups": 0,
        "user_updates": 2000,
    },
    {
        "table_schema": "dbo",
        "table_name": "Attendance",
        "index_name": "IX_Old_Attendance",
        "index_type": "NONCLUSTERED",
        "is_unique": False,
        "is_primary_key": False,
        "columns": "OldColumn",
        "user_seeks": 0,
        "user_scans": 0,
        "user_lookups": 0,
        "user_updates": 500,
    },
    {
        "table_schema": "dbo",
        "table_name": "Enrollments",
        "index_name": "IX_Dup_Enrollments",
        "index_type": "NONCLUSTERED",
        "is_unique": False,
        "is_primary_key": False,
        "columns": "CourseId",
        "user_seeks": 100,
        "user_scans": 5,
        "user_lookups": 0,
        "user_updates": 2000,
    },
]

MOCK_MISSING_INDEXES = [
    {
        "table_name": "[dbo].[Grades]",
        "equality_columns": "[StudentId], [CourseId]",
        "inequality_columns": None,
        "included_columns": "[Grade]",
        "improvement_measure": 85432.5,
        "user_seeks": 12000,
        "user_scans": 500,
    },
    {
        "table_name": "[dbo].[Payments]",
        "equality_columns": "[StudentId]",
        "inequality_columns": "[PaymentDate]",
        "included_columns": None,
        "improvement_measure": 42100.0,
        "user_seeks": 8000,
        "user_scans": 200,
    },
]

MOCK_TABLE_SIZES = [
    {
        "table_schema": "dbo",
        "table_name": "Grades",
        "row_count": 90000,
        "total_space_kb": 15360,
        "used_space_kb": 14000,
    },
    {
        "table_schema": "dbo",
        "table_name": "Enrollments",
        "row_count": 45000,
        "total_space_kb": 8192,
        "used_space_kb": 7500,
    },
    {
        "table_schema": "dbo",
        "table_name": "Payments",
        "row_count": 32000,
        "total_space_kb": 6144,
        "used_space_kb": 5800,
    },
    {
        "table_schema": "dbo",
        "table_name": "Students",
        "row_count": 15000,
        "total_space_kb": 4096,
        "used_space_kb": 3800,
    },
    {
        "table_schema": "dbo",
        "table_name": "Courses",
        "row_count": 200,
        "total_space_kb": 128,
        "used_space_kb": 100,
    },
    {
        "table_schema": "dbo",
        "table_name": "Departments",
        "row_count": 12,
        "total_space_kb": 64,
        "used_space_kb": 16,
    },
]

MOCK_PERMISSIONS = [
    {
        "principal_name": "app_user",
        "principal_type": "SQL_USER",
        "permission_name": "SELECT",
        "permission_state": "GRANT",
        "object_name": "Students",
        "class_desc": "OBJECT_OR_COLUMN",
    },
    {
        "principal_name": "admin_role",
        "principal_type": "DATABASE_ROLE",
        "permission_name": "CONTROL",
        "permission_state": "GRANT",
        "object_name": None,
        "class_desc": "DATABASE",
    },
]
