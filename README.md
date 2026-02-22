# SQLForensic

> Reverse-engineer any database in minutes. Schema analysis, dead code detection,
> dependency graphs, schema diff with migration scripts, and actionable recommendations — all from one command.

[![CI](https://github.com/mcandiri/sqlforensic/actions/workflows/ci.yml/badge.svg)](https://github.com/mcandiri/sqlforensic/actions)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)
![Tests](https://img.shields.io/badge/tests-289%20passing-brightgreen)
![Coverage](https://img.shields.io/badge/coverage-73%25-green)
![Type Checked](https://img.shields.io/badge/mypy-strict-blue)

---

## The Problem

You just inherited a database with 500 tables, 2000 stored procedures, and zero documentation.
Understanding it manually takes days. **SQLForensic does it in minutes.**

## Quick Start

```bash
pip install sqlforensic

# Full scan with console output
sqlforensic scan --server "localhost" --database "MyDB" --user "sa" --password "***"

# Generate interactive HTML report
sqlforensic scan --server "localhost" --database "MyDB" --user "sa" --password "***" \
    --output report.html --format html
```

## Demo Output

Open the example reports in `examples/sample_output/` to see what SQLForensic produces — no database connection needed:

- **[report.html](examples/sample_output/report.html)** — Full interactive dashboard with schema browser, dependency graph, and issue tracking
- **[dependency_graph.html](examples/sample_output/dependency_graph.html)** — Interactive D3.js force-directed dependency visualization
- **[report.md](examples/sample_output/report.md)** — Markdown documentation
- **[report.json](examples/sample_output/report.json)** — Machine-readable JSON export
- **[diff_report.md](examples/sample_output/diff_report.md)** — Schema diff report between two databases
- **[migration.sql](examples/sample_output/migration.sql)** — Safe-mode migration script with rollback

### Console Output Preview

```
╔══════════════════════════════════════════════════════════════╗
║                    SQLForensic Report                       ║
║                    Database: SchoolDB                       ║
║                    Provider: SQL Server                     ║
╚══════════════════════════════════════════════════════════════╝

┌─────────────────────────────────────────────────────────────┐
│ DATABASE HEALTH SCORE: 68/100                               │
│ ██████████████████████████████████░░░░░░░░░░░░░░░░ GOOD     │
└─────────────────────────────────────────────────────────────┘

📊 SCHEMA OVERVIEW
┌──────────────────┬───────┐
│ Metric           │ Count │
├──────────────────┼───────┤
│ Tables           │    15 │
│ Views            │     5 │
│ Stored Procedures│    30 │
│ Indexes          │    45 │
│ Foreign Keys     │    18 │
│ Total Columns    │   285 │
│ Total Rows       │ 2.4M  │
└──────────────────┴───────┘

⚠️  ISSUES FOUND
┌──────────────────────────────────────────┬──────────┬───────┐
│ Issue                                    │ Severity │ Count │
├──────────────────────────────────────────┼──────────┼───────┤
│ Tables with no primary key               │ HIGH     │ 2     │
│ Missing foreign key indexes              │ HIGH     │ 8     │
│ Unused stored procedures                 │ MEDIUM   │ 5     │
│ Circular dependencies detected           │ HIGH     │ 1     │
│ SPs with complexity score > 50           │ MEDIUM   │ 4     │
└──────────────────────────────────────────┴──────────┴───────┘

🔗 TOP DEPENDENCY HOTSPOTS
┌──────────────────┬──────────────┬──────────────────────────┐
│ Table            │ Dependent SPs│ Risk Level               │
├──────────────────┼──────────────┼──────────────────────────┤
│ Students         │ 22           │ 🔴 CRITICAL              │
│ Courses          │ 18           │ 🔴 CRITICAL              │
│ Enrollments      │ 14           │ 🟡 HIGH                  │
│ Users            │ 11           │ 🟡 HIGH                  │
│ Grades           │ 9            │ 🟢 MEDIUM                │
└──────────────────┴──────────────┴──────────────────────────┘
```

## Features

### Full Database Scan

```bash
# SQL Server
sqlforensic scan --server "localhost" --database "MyDB" --user "sa" --password "***"

# PostgreSQL
sqlforensic scan --provider postgresql --host "localhost" --database "mydb" --user "postgres" --password "***"

# With connection string
sqlforensic scan --connection-string "Server=localhost;Database=MyDB;Trusted_Connection=True;"

# Output formats
sqlforensic scan -s "..." -d "..." --output report.html --format html
sqlforensic scan -s "..." -d "..." --output report.md --format markdown
sqlforensic scan -s "..." -d "..." --output report.json --format json
```

### Individual Analyzers

```bash
sqlforensic schema -s "..." -d "..."          # Schema overview
sqlforensic relationships -s "..." -d "..."   # FK + implicit relationships
sqlforensic procedures -s "..." -d "..."      # SP complexity & dependencies
sqlforensic indexes -s "..." -d "..."         # Missing, unused, duplicate indexes
sqlforensic deadcode -s "..." -d "..."        # Unused tables, SPs, orphan columns
sqlforensic graph -s "..." -d "..." -o g.html # Interactive dependency graph
sqlforensic impact -s "..." -d "..." -t "Students"  # Impact analysis
sqlforensic health -s "..." -d "..."          # Health score
sqlforensic diff --source-database "..." --target-database "..."  # Schema diff
```

### Schema Analysis
- All tables with columns, types, nullability, defaults
- Primary keys, foreign keys, unique constraints
- Views with underlying queries
- Row counts and approximate table sizes

### Relationship Discovery
- **Explicit:** Foreign key constraints (100% confidence)
- **SP-based:** Table joins found in stored procedure code (80% confidence)
- **Naming-based:** Column naming conventions like `StudentId` → `Students.Id` (60% confidence)

### Stored Procedure Analysis
- Complexity scoring based on JOINs, subquery depth, cursors, temp tables, dynamic SQL
- Categorized: Simple (< 20), Medium (20–50), Complex (> 50)
- Anti-pattern detection: `SELECT *`, `NOLOCK` hints, cursors, unsafe dynamic SQL
- CRUD operation extraction per table

### Index Analysis & Recommendations
- Missing indexes with ready-to-run `CREATE INDEX` statements
- Unused indexes with `DROP INDEX` statements
- Duplicate and overlapping index detection
- Impact-based prioritization

### Dead Code Detection
- Unused tables (no FK references, not in any SP/view)
- Unused stored procedures (not called by other SPs)
- Orphan columns (not referenced in any SP or view)
- Empty tables (0 rows)

### Interactive Dependency Graph
- D3.js force-directed visualization
- Nodes colored by type (table, SP, view) and sized by criticality
- Hover to highlight connections, click for details
- Zoom, pan, drag, and filter controls

### Impact Analysis

```bash
sqlforensic impact -s "..." -d "..." --table "Students"
# Shows: All SPs, views, and tables that depend on Students
# Risk level: CRITICAL (22 dependent stored procedures)
```

### Health Score (0–100)
Weighted scoring based on:
- Tables without PK (−5 each)
- Missing FK indexes (−2 each)
- Dead procedures (−1 each)
- Circular dependencies (−10 each)
- High-complexity SPs (−2 each)
- Bonus: Good FK coverage, consistent naming

### Schema Diff & Migration

Compare two database schemas and generate safe migration scripts:

```bash
sqlforensic diff \
    --source-server "dev" --source-database "SchoolDB_Dev" \
    --target-server "prod" --target-database "SchoolDB_Prod" \
    --user "sa" --password "***" \
    --output migration.sql --format sql --safe-mode
```

Every change gets a **risk score** based on dependency analysis:

| Change | Risk | Why |
|---|---|---|
| Drop column `Students.LegacyCode` | CRITICAL | 2 SPs + 1 View reference it |
| Alter `Students.Email` type | HIGH | Possible data truncation |
| Add table `CourseCategories` | NONE | No dependencies |

Output formats: `console`, `html`, `markdown`, `json`, `sql` (migration script only).

Migration scripts include transaction safety, data validation, and manual review flags for risky changes.

## Python Library API

```python
from sqlforensic import DatabaseForensic

# Connect and analyze
forensic = DatabaseForensic(
    provider="sqlserver",
    server="localhost",
    database="SchoolDB",
    username="sa",
    password="your-password"
)

# Full analysis
report = forensic.analyze()
print(f"Health Score: {report.health_score}/100")
print(f"Tables: {len(report.tables)}")
print(f"Dead SPs: {len(report.dead_procedures)}")
print(f"Missing Indexes: {len(report.missing_indexes)}")

# Individual analyzers
schema = forensic.analyze_schema()
relationships = forensic.analyze_relationships()
dead_code = forensic.detect_dead_code()
dependencies = forensic.analyze_dependencies()
indexes = forensic.analyze_indexes()

# Impact analysis
impact = forensic.impact_analysis("Students")
print(f"Changing 'Students' would affect {impact.total_affected} objects")
for sp in impact.affected_sps:
    print(f"  - {sp['name']} (risk: {sp['risk_level']})")

# Export reports
forensic.export_html("report.html")
forensic.export_markdown("report.md")
forensic.export_json("report.json")
forensic.export_dependency_graph("graph.html")

# Schema diff
target = DatabaseForensic(
    provider="sqlserver",
    server="prod-server",
    database="SchoolDB_Prod",
    username="sa",
    password="your-password"
)
diff = forensic.diff(target)
print(f"Changes: {diff.total_changes}, Risk: {diff.risk_level}")
```

## Supported Databases

| Database | Version | Connector |
|----------|---------|-----------|
| SQL Server | 2016+ | pyodbc |
| PostgreSQL | 12+ | psycopg2 |

## Born From Production

> SQLForensic was built from years of experience managing databases powering enterprise
> platforms with 500+ tables and thousands of stored procedures. Every analyzer addresses
> a real pain point encountered in production database management.

## Security

- **Read-only** — never modifies your database (all queries are SELECT only)
- **Passwords never logged** — connection strings are masked in all output
- **Supports trusted connections** — Windows authentication for SQL Server
- **SSL/TLS support** — encrypted connections to your database

## Development

```bash
# Clone and install
git clone https://github.com/mcandiri/sqlforensic.git
cd sqlforensic
make install-dev

# Run tests (no database needed)
make test

# Lint and type check
make lint
make type-check

# Run all checks
make all
```

## Project Structure

```
SQLForensic/
├── src/sqlforensic/
│   ├── cli.py                    # CLI entry point (Click)
│   ├── config.py                 # Connection & analysis settings
│   ├── connectors/               # Database connectors (SQL Server, PostgreSQL)
│   ├── analyzers/                # 9 specialized analyzers (incl. diff)
│   ├── diff/                     # Schema diff engine & migration generator
│   ├── parsers/                  # SQL parser for SP analysis
│   ├── scoring/                  # Health score & risk scoring
│   ├── reporters/                # Console, HTML, Markdown, JSON reporters
│   └── utils/                    # SQL patterns & formatting helpers
├── tests/                        # 289 tests (all run without a database)
├── examples/sample_output/       # Pre-generated example reports & diff samples
├── pyproject.toml                # Modern Python packaging
└── Makefile
```

## Roadmap

- [ ] MySQL / MariaDB support
- [ ] Azure SQL Database support
- [x] Schema comparison between two databases
- [ ] Automated documentation generation with AI summaries
- [ ] VS Code extension
- [ ] GitHub Action for CI/CD database health checks

## Contributing

Contributions are welcome! Please open an issue first to discuss what you'd like to change.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Run tests (`make test`)
4. Commit your changes
5. Open a Pull Request

## License

[MIT](LICENSE) — Mehmet Can Diri
