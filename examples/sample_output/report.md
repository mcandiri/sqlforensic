# SQLForensic Report: SchoolDB

**Provider:** SQL Server
**Generated:** 2026-02-22 14:35:17
**Health Score:** 68/100

## Schema Overview

| Metric | Count |
|--------|------:|
| Tables | 15 |
| Views | 5 |
| Stored Procedures | 30 |
| Functions | 8 |
| Indexes | 45 |
| Foreign Keys | 18 |
| Columns | 285 |
| Total Rows | 2.4M |

### Tables

| Schema | Table | Columns | Rows | PK |
|--------|-------|--------:|-----:|:--:|
| dbo | Students | 22 | 45.2K | Yes |
| dbo | Teachers | 18 | 1,320 | Yes |
| dbo | Courses | 14 | 2,450 | Yes |
| dbo | Enrollments | 8 | 312.5K | Yes |
| dbo | Grades | 12 | 1.2M | Yes |
| dbo | Payments | 16 | 189.4K | Yes |
| dbo | Departments | 10 | 42 | Yes |
| dbo | Classrooms | 9 | 185 | Yes |
| dbo | Schedules | 15 | 18.7K | Yes |
| dbo | Attendance | 11 | 486.3K | Yes |
| dbo | Exams | 13 | 3,240 | Yes |
| dbo | ExamResults | 10 | 156.8K | Yes |
| dbo | Assignments | 14 | 9,870 | Yes |
| dbo | Submissions | 18 | 87.6K | Yes |
| dbo | Users | 20 | 47.1K | Yes |
| staging | Logs_Archive | 24 | 524 | **No** |
| staging | TempImport | 31 | 0 | **No** |

## Issues

| Issue | Severity | Count |
|-------|----------|------:|
| Tables with no primary key | HIGH | 2 |
| Missing foreign key indexes | HIGH | 5 |
| Circular dependencies detected | HIGH | 2 |
| SPs with complexity score > 50 | MEDIUM | 3 |
| Unused stored procedures | MEDIUM | 5 |
| Duplicate indexes | MEDIUM | 2 |
| Tables with no relationships | MEDIUM | 3 |
| Empty tables (0 rows) | LOW | 1 |

## Relationships

### Foreign Keys (8)

| Parent Table | Column | Referenced Table | Referenced Column |
|-------------|--------|-----------------|-------------------|
| dbo.Enrollments | StudentId | dbo.Students | StudentId |
| dbo.Enrollments | CourseId | dbo.Courses | CourseId |
| dbo.Grades | EnrollmentId | dbo.Enrollments | EnrollmentId |
| dbo.Grades | ExamId | dbo.Exams | ExamId |
| dbo.Courses | DepartmentId | dbo.Departments | DepartmentId |
| dbo.Schedules | CourseId | dbo.Courses | CourseId |
| dbo.Schedules | ClassroomId | dbo.Classrooms | ClassroomId |
| dbo.Payments | StudentId | dbo.Students | StudentId |

### Implicit Relationships (4)

| Parent | Column | Referenced | Confidence | Source |
|--------|--------|-----------|:----------:|--------|
| dbo.Attendance | StudentId | dbo.Students | 95% | naming_convention |
| dbo.Submissions | AssignmentId | dbo.Assignments | 92% | naming_convention |
| dbo.ExamResults | StudentId | dbo.Students | 90% | naming_convention |
| dbo.Assignments | CourseId | dbo.Courses | 88% | naming_convention |

## Stored Procedure Analysis

| Name | Lines | Joins | Tables | Complexity | Score |
|------|------:|------:|-------:|------------|------:|
| usp_GenerateTranscript | 287 | 8 | 6 | High | 72 |
| usp_CalculateGPA | 195 | 5 | 4 | High | 58 |
| usp_ProcessPaymentBatch | 163 | 4 | 3 | High | 54 |
| usp_EnrollStudent | 124 | 3 | 5 | Medium | 42 |
| usp_GetAttendanceReport | 112 | 4 | 3 | Medium | 38 |
| usp_SubmitExamResults | 98 | 3 | 4 | Medium | 35 |
| usp_UpdateSchedule | 85 | 2 | 3 | Medium | 28 |
| usp_AssignTeacher | 72 | 2 | 2 | Simple | 18 |
| usp_GetStudentProfile | 64 | 3 | 2 | Simple | 16 |
| usp_ArchiveOldRecords | 56 | 1 | 2 | Simple | 12 |

## Index Analysis

### Missing Indexes (5)

- **dbo.Grades**: EnrollmentId
  ```sql
  CREATE INDEX [IX_Grades_EnrollmentId] ON [dbo.Grades] (EnrollmentId);
  ```
- **dbo.Attendance**: StudentId, CourseId
  ```sql
  CREATE INDEX [IX_Attendance_StudentId_CourseId] ON [dbo.Attendance] (StudentId, CourseId);
  ```
- **dbo.Submissions**: AssignmentId
  ```sql
  CREATE INDEX [IX_Submissions_AssignmentId] ON [dbo.Submissions] (AssignmentId);
  ```
- **dbo.ExamResults**: StudentId
  ```sql
  CREATE INDEX [IX_ExamResults_StudentId] ON [dbo.ExamResults] (StudentId) INCLUDE (Score, GradeLetter);
  ```
- **dbo.Payments**: StudentId, PaymentDate
  ```sql
  CREATE INDEX [IX_Payments_StudentId_PaymentDate] ON [dbo.Payments] (StudentId, PaymentDate) INCLUDE (Amount, Status);
  ```

### Unused Indexes (3)

- `IX_Students_LegacyId` on `dbo.Students`
- `IX_Courses_OldCategoryCode` on `dbo.Courses`
- `IX_Enrollments_ImportBatch` on `dbo.Enrollments`

### Duplicate Indexes (2)

- `IX_Grades_StudentId` duplicates `IX_Grades_StudentId_ExamId` on `dbo.Grades`
- `IX_Schedules_Day` duplicates `IX_Schedules_Day_Period` on `dbo.Schedules`

## Dead Code

### Unreferenced Tables (3)

- `staging.Logs_Archive` (524 rows)
- `staging.TempImport` (0 rows)
- `dbo.Config_Backup` (18 rows)

### Unused Procedures (5)

- `dbo.usp_MigrateV1Students`
- `dbo.usp_FixDuplicateEnrollments`
- `dbo.usp_TempReportQ3`
- `dbo.usp_OldPaymentReconcile`
- `dbo.usp_CleanupTestData`

## Dependencies

### Circular Dependencies (2)

- dbo.Enrollments -> dbo.Grades -> dbo.ExamResults -> dbo.Enrollments
- dbo.Schedules -> dbo.Courses -> dbo.Teachers -> dbo.Schedules

### Dependency Hotspots

| Table | Dependent SPs | Risk |
|-------|-------------:|------|
| dbo.Students | 18 | HIGH |
| dbo.Enrollments | 14 | HIGH |
| dbo.Courses | 12 | MEDIUM |
| dbo.Grades | 9 | MEDIUM |
| dbo.Payments | 6 | LOW |

---
*Generated by [SQLForensic](https://github.com/mehmetcandiri/sqlforensic)*
