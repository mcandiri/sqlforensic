"""Regex patterns for SQL analysis.

All patterns are pre-compiled or stored as raw strings for use with
re.compile/re.findall/re.search with appropriate flags.
"""

from __future__ import annotations

# Table references in FROM clauses (captures schema.table or table)
TABLE_REF_PATTERN = r"(?:FROM|INTO|UPDATE)\s+(?:\[?(\w+)\]?\.)?(\[?\w+\]?)"

# JOIN patterns (all join types)
JOIN_PATTERN = r"(?:INNER|LEFT|RIGHT|FULL|CROSS)?\s*JOIN\s+(?:\[?(\w+)\]?\.)?(\[?\w+\]?)"

# SELECT ... FROM table
SELECT_FROM_PATTERN = r"FROM\s+(?:\[?\w+\]?\.)?\[?(\w+)\]?"

# INSERT INTO table
INSERT_PATTERN = r"INSERT\s+INTO\s+(?:\[?\w+\]?\.)?\[?(\w+)\]?"

# UPDATE table
UPDATE_PATTERN = r"UPDATE\s+(?:\[?\w+\]?\.)?\[?(\w+)\]?"

# DELETE FROM table
DELETE_PATTERN = r"DELETE\s+(?:FROM\s+)?(?:\[?\w+\]?\.)?\[?(\w+)\]?"

# Subquery detection
SUBQUERY_PATTERN = r"\(\s*SELECT\b"

# Cursor usage
CURSOR_PATTERN = r"\bDECLARE\s+\w+\s+CURSOR\b|\bOPEN\s+\w+|\bFETCH\s+(?:NEXT\s+)?FROM\b"

# Dynamic SQL with string concatenation or variable execution
DYNAMIC_SQL_PATTERN = r"\bEXEC(?:UTE)?\s*\(\s*(?:@\w+|['\"])|EXEC\s+(?:sp_executesql\s+)?@"

# Temporary tables
TEMP_TABLE_PATTERN = r"(?:CREATE\s+TABLE\s+)?#\w+|DECLARE\s+@\w+\s+TABLE"

# CASE statements
CASE_PATTERN = r"\bCASE\b"

# SELECT * anti-pattern
SELECT_STAR_PATTERN = r"\bSELECT\s+\*\s+FROM\b"

# NOLOCK hint
NOLOCK_PATTERN = r"\bWITH\s*\(\s*NOLOCK\s*\)|\bNOLOCK\b"

# Column naming pattern for implicit FK detection (e.g., StudentId -> Students)
FK_NAMING_PATTERN = r"(\w+)(?:Id|_id|ID)$"

# Schema-qualified name
SCHEMA_QUALIFIED_PATTERN = r"\[?(\w+)\]?\.\[?(\w+)\]?"
