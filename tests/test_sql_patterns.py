"""Tests for SQL regex patterns in sql_patterns.py."""

from __future__ import annotations

import re

from sqlforensic.utils.sql_patterns import (
    CASE_PATTERN,
    CURSOR_PATTERN,
    DELETE_PATTERN,
    DYNAMIC_SQL_PATTERN,
    FK_NAMING_PATTERN,
    INSERT_PATTERN,
    JOIN_PATTERN,
    NOLOCK_PATTERN,
    SCHEMA_QUALIFIED_PATTERN,
    SELECT_FROM_PATTERN,
    SELECT_STAR_PATTERN,
    SUBQUERY_PATTERN,
    TABLE_REF_PATTERN,
    TEMP_TABLE_PATTERN,
    UPDATE_PATTERN,
)


class TestTableRefPattern:
    def test_from_simple(self) -> None:
        assert re.search(TABLE_REF_PATTERN, "FROM Students", re.IGNORECASE)

    def test_from_schema_qualified(self) -> None:
        m = re.search(TABLE_REF_PATTERN, "FROM dbo.Students", re.IGNORECASE)
        assert m
        assert m.group(1) == "dbo"

    def test_insert_into(self) -> None:
        assert re.search(TABLE_REF_PATTERN, "INSERT INTO Orders", re.IGNORECASE)

    def test_update(self) -> None:
        assert re.search(TABLE_REF_PATTERN, "UPDATE Users SET x=1", re.IGNORECASE)

    def test_bracketed_names(self) -> None:
        assert re.search(TABLE_REF_PATTERN, "FROM [dbo].[Students]", re.IGNORECASE)


class TestJoinPattern:
    def test_inner_join(self) -> None:
        m = re.search(JOIN_PATTERN, "INNER JOIN Courses ON 1=1", re.IGNORECASE)
        assert m

    def test_left_join(self) -> None:
        assert re.search(JOIN_PATTERN, "LEFT JOIN Grades g ON 1=1", re.IGNORECASE)

    def test_cross_join(self) -> None:
        assert re.search(JOIN_PATTERN, "CROSS JOIN Ref", re.IGNORECASE)

    def test_plain_join(self) -> None:
        assert re.search(JOIN_PATTERN, "JOIN Users u ON 1=1", re.IGNORECASE)


class TestSelectFromPattern:
    def test_simple(self) -> None:
        m = re.search(SELECT_FROM_PATTERN, "SELECT * FROM Students", re.IGNORECASE)
        assert m
        assert m.group(1) == "Students"

    def test_schema_qualified(self) -> None:
        m = re.search(SELECT_FROM_PATTERN, "FROM dbo.Orders", re.IGNORECASE)
        assert m
        assert m.group(1) == "Orders"


class TestCrudPatterns:
    def test_insert(self) -> None:
        m = re.search(INSERT_PATTERN, "INSERT INTO Enrollments (Col) VALUES (1)", re.IGNORECASE)
        assert m
        assert m.group(1) == "Enrollments"

    def test_update(self) -> None:
        m = re.search(UPDATE_PATTERN, "UPDATE Payments SET Amount=0", re.IGNORECASE)
        assert m
        assert m.group(1) == "Payments"

    def test_delete_with_from(self) -> None:
        m = re.search(DELETE_PATTERN, "DELETE FROM AuditLog WHERE 1=0", re.IGNORECASE)
        assert m
        assert m.group(1) == "AuditLog"

    def test_delete_without_from(self) -> None:
        m = re.search(DELETE_PATTERN, "DELETE Logs WHERE Id=1", re.IGNORECASE)
        assert m
        assert m.group(1) == "Logs"


class TestAntiPatterns:
    def test_select_star(self) -> None:
        assert re.search(SELECT_STAR_PATTERN, "SELECT * FROM T", re.IGNORECASE)

    def test_select_columns_no_match(self) -> None:
        assert not re.search(SELECT_STAR_PATTERN, "SELECT a, b FROM T", re.IGNORECASE)

    def test_nolock_hint(self) -> None:
        assert re.search(NOLOCK_PATTERN, "FROM T WITH (NOLOCK)", re.IGNORECASE)

    def test_nolock_standalone(self) -> None:
        assert re.search(NOLOCK_PATTERN, "FROM T NOLOCK", re.IGNORECASE)

    def test_cursor_declare(self) -> None:
        assert re.search(CURSOR_PATTERN, "DECLARE c CURSOR FOR SELECT 1", re.IGNORECASE)

    def test_cursor_fetch(self) -> None:
        assert re.search(CURSOR_PATTERN, "FETCH NEXT FROM c", re.IGNORECASE)


class TestDynamicSqlPattern:
    def test_exec_variable(self) -> None:
        assert re.search(DYNAMIC_SQL_PATTERN, "EXEC(@sql)", re.IGNORECASE)

    def test_execute_string(self) -> None:
        assert re.search(DYNAMIC_SQL_PATTERN, "EXEC('SELECT 1')", re.IGNORECASE)

    def test_sp_executesql(self) -> None:
        assert re.search(DYNAMIC_SQL_PATTERN, "EXEC sp_executesql @sql", re.IGNORECASE)

    def test_plain_exec_no_match(self) -> None:
        assert not re.search(DYNAMIC_SQL_PATTERN, "EXEC sp_GetData", re.IGNORECASE)


class TestOtherPatterns:
    def test_subquery(self) -> None:
        assert re.search(SUBQUERY_PATTERN, "WHERE x IN ( SELECT 1)", re.IGNORECASE)

    def test_temp_table_hash(self) -> None:
        assert re.search(TEMP_TABLE_PATTERN, "CREATE TABLE #Temp (Id INT)", re.IGNORECASE)

    def test_table_variable(self) -> None:
        assert re.search(TEMP_TABLE_PATTERN, "DECLARE @tbl TABLE", re.IGNORECASE)

    def test_case(self) -> None:
        assert re.search(CASE_PATTERN, "CASE WHEN 1=1 THEN 'Y' END", re.IGNORECASE)


class TestFKNamingPattern:
    def test_student_id(self) -> None:
        m = re.match(FK_NAMING_PATTERN, "StudentId")
        assert m
        assert m.group(1) == "Student"

    def test_underscore_id(self) -> None:
        m = re.match(FK_NAMING_PATTERN, "course_id")
        assert m
        assert m.group(1) == "course"

    def test_upper_id(self) -> None:
        m = re.match(FK_NAMING_PATTERN, "DepartmentID")
        assert m
        assert m.group(1) == "Department"

    def test_no_match_plain_name(self) -> None:
        assert not re.match(FK_NAMING_PATTERN, "FirstName")

    def test_no_match_just_id(self) -> None:
        assert not re.match(FK_NAMING_PATTERN, "Id")


class TestSchemaQualifiedPattern:
    def test_dbo_table(self) -> None:
        m = re.search(SCHEMA_QUALIFIED_PATTERN, "dbo.Students")
        assert m
        assert m.group(1) == "dbo"
        assert m.group(2) == "Students"

    def test_bracketed(self) -> None:
        m = re.search(SCHEMA_QUALIFIED_PATTERN, "[dbo].[Students]")
        assert m
