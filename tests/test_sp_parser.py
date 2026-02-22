"""Tests for SPParser — SQL stored procedure body parsing."""

from __future__ import annotations

from sqlforensic.parsers.sp_parser import SPParser, SPParseResult


class TestSPParser:
    """Tests for stored procedure parsing and pattern detection."""

    def setup_method(self) -> None:
        self.parser = SPParser()

    def test_empty_body_returns_default_result(self) -> None:
        """An SP with no ROUTINE_DEFINITION should return an empty SPParseResult."""
        sp = {
            "ROUTINE_SCHEMA": "dbo",
            "ROUTINE_NAME": "sp_Empty",
            "ROUTINE_DEFINITION": None,
        }
        result = self.parser.parse(sp)

        assert isinstance(result, SPParseResult)
        assert result.name == "sp_Empty"
        assert result.schema == "dbo"
        assert result.line_count == 0
        assert result.complexity_score == 0
        assert result.complexity_category == "Simple"

    def test_select_star_detected_as_anti_pattern(self) -> None:
        """SELECT * FROM should be flagged as an anti-pattern."""
        sp = {
            "ROUTINE_SCHEMA": "dbo",
            "ROUTINE_NAME": "sp_BadSelect",
            "ROUTINE_DEFINITION": """
CREATE PROCEDURE [dbo].[sp_BadSelect]
AS
BEGIN
    SELECT * FROM Students
END
""",
        }
        result = self.parser.parse(sp)

        assert any("SELECT *" in ap for ap in result.anti_patterns)

    def test_cursor_detected_as_anti_pattern(self) -> None:
        """DECLARE ... CURSOR should be flagged as anti-pattern."""
        sp = {
            "ROUTINE_SCHEMA": "dbo",
            "ROUTINE_NAME": "sp_CursorUser",
            "ROUTINE_DEFINITION": """
CREATE PROCEDURE [dbo].[sp_CursorUser]
AS
BEGIN
    DECLARE my_cursor CURSOR FOR
    SELECT Id FROM Students
    OPEN my_cursor
    FETCH NEXT FROM my_cursor
    CLOSE my_cursor
    DEALLOCATE my_cursor
END
""",
        }
        result = self.parser.parse(sp)

        assert result.has_cursors is True
        assert any("Cursor" in ap for ap in result.anti_patterns)

    def test_join_count_extracted(self) -> None:
        """JOIN count should match the number of JOIN clauses."""
        sp = {
            "ROUTINE_SCHEMA": "dbo",
            "ROUTINE_NAME": "sp_Joins",
            "ROUTINE_DEFINITION": """
CREATE PROCEDURE [dbo].[sp_Joins]
AS
BEGIN
    SELECT a.Id, b.Name, c.Value
    FROM TableA a
    INNER JOIN TableB b ON a.Id = b.AId
    LEFT JOIN TableC c ON b.Id = c.BId
END
""",
        }
        result = self.parser.parse(sp)

        assert result.join_count == 2

    def test_complexity_categorization(self) -> None:
        """Complexity categories should map: <20=Simple, 20-49=Medium, >=50=Complex."""
        assert self.parser._categorize_complexity(5) == "Simple"
        assert self.parser._categorize_complexity(19) == "Simple"
        assert self.parser._categorize_complexity(20) == "Medium"
        assert self.parser._categorize_complexity(49) == "Medium"
        assert self.parser._categorize_complexity(50) == "Complex"
        assert self.parser._categorize_complexity(100) == "Complex"

    def test_crud_operations_extracted(self) -> None:
        """INSERT, UPDATE, DELETE, and SELECT operations should be extracted correctly."""
        sp = {
            "ROUTINE_SCHEMA": "dbo",
            "ROUTINE_NAME": "sp_CRUD",
            "ROUTINE_DEFINITION": """
CREATE PROCEDURE [dbo].[sp_CRUD]
AS
BEGIN
    SELECT Id FROM Students
    INSERT INTO Enrollments (StudentId) VALUES (1)
    UPDATE Payments SET Amount = 100
    DELETE FROM AuditLog WHERE Id = 1
END
""",
        }
        result = self.parser.parse(sp)

        assert "Students" in result.crud_operations["SELECT"]
        assert "Enrollments" in result.crud_operations["INSERT"]
        assert "Payments" in result.crud_operations["UPDATE"]
        assert "AuditLog" in result.crud_operations["DELETE"]
