"""
SQLForensic -- Demo Analysis Script

This script demonstrates how to use SQLForensic as a Python library to
analyze a database programmatically. It covers the full API surface:
creating a connection, running analyses, accessing results, and exporting
reports in multiple formats.

NOTE: This is a demonstration script. It requires a real database connection
to run. Replace the placeholder connection values with your own credentials
before executing.
"""

from dataclasses import asdict

from sqlforensic import AnalysisReport, DatabaseForensic, ImpactResult

# ---------------------------------------------------------------------------
# 1. Create a DatabaseForensic instance
# ---------------------------------------------------------------------------
# Provide connection details for your target database. SQLForensic supports
# both SQL Server and PostgreSQL.

# SQL Server example:
forensic = DatabaseForensic(
    provider="sqlserver",
    server="your-server.example.com",
    database="YourDatabase",
    username="your_username",
    password="your_password",
    port=1433,
)

# PostgreSQL example (uncomment to use):
# forensic = DatabaseForensic(
#     provider="postgresql",
#     server="your-server.example.com",
#     database="your_database",
#     username="your_username",
#     password="your_password",
#     port=5432,
#     ssl=True,
# )

# You can also connect using a raw connection string:
# forensic = DatabaseForensic(
#     provider="sqlserver",
#     connection_string="Driver={ODBC Driver 17 for SQL Server};"
#                       "Server=localhost;Database=MyDB;"
#                       "UID=sa;PWD=secret;",
# )

# Or with Windows trusted authentication (SQL Server only):
# forensic = DatabaseForensic(
#     provider="sqlserver",
#     server="localhost",
#     database="MyDB",
#     trusted_connection=True,
# )


# ---------------------------------------------------------------------------
# 2. Run a full analysis
# ---------------------------------------------------------------------------
# The analyze() method connects to the database, runs every analyzer
# (schema, relationships, indexes, dead code, dependencies, security, etc.),
# computes a health score, and returns a comprehensive AnalysisReport.

report: AnalysisReport = forensic.analyze()


# ---------------------------------------------------------------------------
# 3. Access results programmatically
# ---------------------------------------------------------------------------

# Overall health score (0-100)
print(f"Database Health Score: {report.health_score}/100")

# Schema overview counts
print(f"Schema Overview: {report.schema_overview}")

# Tables discovered
print(f"\nTotal tables: {len(report.tables)}")
for table in report.tables[:5]:
    print(
        f"  - {table.get('TABLE_SCHEMA', '')}.{table.get('TABLE_NAME', '')}"
        f"  ({table.get('column_count', 0)} columns, "
        f"{table.get('row_count', 0)} rows)"
    )

# Stored procedures
print(f"\nStored procedures: {len(report.stored_procedures)}")

# Views
print(f"Views: {len(report.views)}")

# Dead (unused) stored procedures
print(f"\nDead procedures: {len(report.dead_procedures)}")
for sp in report.dead_procedures:
    print(f"  - {sp.get('ROUTINE_SCHEMA', '')}.{sp.get('ROUTINE_NAME', '')}")

# Missing indexes -- these are indexes the database engine recommends adding
print(f"\nMissing indexes: {len(report.missing_indexes)}")
for idx in report.missing_indexes[:5]:
    print(
        f"  - Table: {idx.get('table_name', '')}, "
        f"Columns: {idx.get('equality_columns', '')}, "
        f"Impact: {idx.get('improvement_measure', 0):.0f}"
    )

# Unused indexes -- these exist but are never read, only costing write overhead
print(f"\nUnused indexes: {len(report.unused_indexes)}")

# Duplicate indexes
print(f"Duplicate indexes: {len(report.duplicate_indexes)}")

# Relationships (foreign keys)
print(f"\nExplicit relationships (FKs): {len(report.relationships)}")
print(f"Implicit relationships (by naming): {len(report.implicit_relationships)}")

# Dead tables (not referenced by any SP, view, or FK)
print(f"\nDead tables: {len(report.dead_tables)}")

# Empty tables
print(f"Empty tables: {len(report.empty_tables)}")

# Circular dependencies
print(f"\nCircular dependencies: {len(report.circular_dependencies)}")

# Security issues
print(f"Security issues: {len(report.security_issues)}")

# Issues summary with severity levels
print(f"\nIssues found: {len(report.issues)}")
for issue in report.issues:
    print(
        f"  [{issue.get('severity', 'INFO')}] {issue.get('description', '')}"
        f" (count: {issue.get('count', 0)})"
    )

# Risk scores
print(f"\nRisk scores: {report.risk_scores}")


# ---------------------------------------------------------------------------
# 4. Run individual analyzers
# ---------------------------------------------------------------------------
# If you only need specific information, you can run individual analyzers
# instead of the full scan. Each method connects, analyzes, and disconnects
# automatically.

# Schema only -- returns tables, views, stored procedures, functions, indexes
schema_result = forensic.analyze_schema()
print(f"\nSchema analysis keys: {list(schema_result.keys())}")

# Relationship discovery -- finds explicit FKs and implicit relationships
rel_result = forensic.analyze_relationships()
print(f"Explicit FKs: {len(rel_result.get('explicit', []))}")
print(f"Implicit relationships: {len(rel_result.get('implicit', []))}")

# Index analysis -- finds missing, unused, and duplicate indexes
index_result = forensic.analyze_indexes()
print(f"Missing indexes: {len(index_result.get('missing', []))}")
print(f"Unused indexes: {len(index_result.get('unused', []))}")
print(f"Duplicate indexes: {len(index_result.get('duplicates', []))}")

# Dead code detection -- finds unreferenced tables, unused SPs, orphan columns
dead_result = forensic.detect_dead_code()
print(f"Dead procedures: {len(dead_result.get('dead_procedures', []))}")
print(f"Dead tables: {len(dead_result.get('dead_tables', []))}")
print(f"Orphan columns: {len(dead_result.get('orphan_columns', []))}")
print(f"Empty tables: {len(dead_result.get('empty_tables', []))}")

# Dependency analysis -- builds dependency graph and finds circular deps
dep_result = forensic.analyze_dependencies()
print(f"Dependency graph entries: {len(dep_result.get('graph', {}))}")
print(f"Circular dependencies: {len(dep_result.get('circular', []))}")


# ---------------------------------------------------------------------------
# 5. Impact analysis
# ---------------------------------------------------------------------------
# Before modifying a table, run impact analysis to understand the blast radius.
# This reveals which stored procedures, views, and related tables would be
# affected.

impact: ImpactResult = forensic.impact_analysis("Orders")

print(f"\nImpact Analysis for table '{impact.table_name}':")
print(f"  Risk level: {impact.risk_level}")
print(f"  Total affected objects: {impact.total_affected}")
print(f"  Affected stored procedures: {len(impact.affected_sps)}")
for sp in impact.affected_sps:
    print(f"    - {sp['name']} (risk: {sp.get('risk_level', 'N/A')})")
print(f"  Affected views: {impact.affected_views}")
print(f"  Affected tables: {impact.affected_tables}")


# ---------------------------------------------------------------------------
# 6. Export to different formats
# ---------------------------------------------------------------------------
# SQLForensic can export a full analysis report in three formats.
# Each export method runs a full analysis internally and writes the output.

# HTML -- interactive dashboard with charts, schema browser, and dependency graph
forensic.export_html("report.html")
print("\nHTML report saved to report.html")

# Markdown -- suitable for project wikis or documentation repos
forensic.export_markdown("report.md")
print("Markdown report saved to report.md")

# JSON -- machine-readable output for CI/CD pipelines and automation
forensic.export_json("report.json")
print("JSON report saved to report.json")

# Interactive dependency graph (standalone HTML with D3.js visualization)
forensic.export_dependency_graph("dependency_graph.html")
print("Dependency graph saved to dependency_graph.html")


# ---------------------------------------------------------------------------
# 7. Working with the report as data
# ---------------------------------------------------------------------------
# The AnalysisReport is a standard Python dataclass, so you can convert it
# to a dictionary or integrate it into your own tooling.

report_dict = asdict(report)
print(f"\nReport dict keys: {list(report_dict.keys())}")

# Example: flag a CI build if health score is below threshold
HEALTH_THRESHOLD = 60
if report.health_score < HEALTH_THRESHOLD:
    print(
        f"\nWARNING: Health score {report.health_score} is below "
        f"threshold {HEALTH_THRESHOLD}. Review the issues above."
    )
