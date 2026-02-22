# Schema Diff Report

**Source:** SchoolDB_Dev (dev-server)
**Target:** SchoolDB_Prod (prod-server)
**Provider:** SQL Server
**Overall Risk:** HIGH
**Total Changes:** 25

---

## Summary

| Object Type | Added | Removed | Modified |
|---|---:|---:|---:|
| Tables | 2 | 0 | 3 |
| Columns | 5 | 2 | 4 |
| Indexes | 5 | 1 | 0 |
| Foreign Keys | 2 | 0 | 0 |
| Stored Procedures | 4 | 1 | 7 |
| Views | 0 | 0 | 1 |
| Functions | 0 | 0 | 0 |

---

## Added Tables

### dbo.CourseCategories

| Column | Type | Nullable | Default |
|---|---|---|---|
| CategoryId | int | No | IDENTITY(1,1) |
| CategoryName | nvarchar(100) | No | |
| Description | nvarchar(500) | Yes | NULL |
| IsActive | bit | No | 1 |
| CreatedDate | datetime2 | No | GETDATE() |
| SortOrder | int | No | 0 |

**Primary Key:** PK_CourseCategories (CategoryId)
**Indexes:** IX_CourseCategories_Name (CategoryName)

### dbo.StudentNotes

| Column | Type | Nullable | Default |
|---|---|---|---|
| NoteId | int | No | IDENTITY(1,1) |
| StudentId | int | No | |
| NoteType | nvarchar(50) | No | 'General' |
| NoteText | nvarchar(max) | No | |
| CreatedBy | int | Yes | NULL |
| CreatedDate | datetime2 | No | GETDATE() |
| IsConfidential | bit | No | 0 |

**Primary Key:** PK_StudentNotes (NoteId)
**Foreign Key:** FK_StudentNotes_Students (StudentId -> Students.StudentId)

---

## Modified Tables

### dbo.Students

**Added Columns:**

| Column | Type | Nullable | Default |
|---|---|---|---|
| MiddleName | nvarchar(100) | Yes | NULL |
| PreferredName | nvarchar(100) | Yes | NULL |

**Removed Columns:**

| Column | Type | Notes |
|---|---|---|
| LegacyCode | varchar(20) | CRITICAL: Referenced by 2 SPs + 1 View |

**Modified Columns:**

| Column | Change | Old | New | Breaking? |
|---|---|---|---|---|
| Email | Type change | nvarchar(100) | nvarchar(255) | No (widening) |
| Phone | Nullability | NOT NULL | NULL | No |

### dbo.Courses

**Added Columns:**

| Column | Type | Nullable | Default |
|---|---|---|---|
| CategoryId | int | Yes | NULL |
| MaxCapacity | int | No | 30 |

**Modified Columns:**

| Column | Change | Old | New | Breaking? |
|---|---|---|---|---|
| CourseName | Length change | nvarchar(100) | nvarchar(200) | No (widening) |

### dbo.Enrollments

**Removed Columns:**

| Column | Type | Notes |
|---|---|---|
| LegacyFlag | bit | LOW: Not referenced by any SP or view |

**Modified Columns:**

| Column | Change | Old | New | Breaking? |
|---|---|---|---|---|
| Grade | Type change | decimal(3,1) | decimal(5,2) | No (widening) |
| Status | Default change | 'Active' | 'Pending' | No |

---

## Index Changes

### Added Indexes

| Table | Index Name | Type | Columns |
|---|---|---|---|
| Students | IX_Students_Email | NONCLUSTERED | Email |
| Students | IX_Students_PreferredName | NONCLUSTERED | PreferredName |
| Courses | IX_Courses_CategoryId | NONCLUSTERED | CategoryId |
| Enrollments | IX_Enrollments_Status | NONCLUSTERED | Status |
| StudentNotes | IX_StudentNotes_StudentId | NONCLUSTERED | StudentId, CreatedDate DESC |

### Removed Indexes

| Table | Index Name | Type | Columns |
|---|---|---|---|
| Students | IX_Students_LegacyCode | NONCLUSTERED | LegacyCode |

---

## Stored Procedure Changes

### Added (4)

| Schema | Name |
|---|---|
| dbo | sp_GetStudentNotes |
| dbo | sp_AddStudentNote |
| dbo | sp_GetCoursesByCategory |
| dbo | sp_UpdateStudentPreferences |

### Removed (1)

| Schema | Name | Risk |
|---|---|---|
| dbo | sp_MigrateLegacyCodes | LOW (utility/migration script) |

### Modified (7)

| Schema | Name | Body Changed |
|---|---|---|
| dbo | sp_GetStudentById | Yes |
| dbo | sp_SearchStudents | Yes |
| dbo | sp_EnrollStudent | Yes |
| dbo | sp_GetEnrollmentReport | Yes |
| dbo | sp_UpdateStudentProfile | Yes |
| dbo | sp_GetCourseRoster | Yes |
| dbo | sp_GenerateTranscript | Yes |

---

## View Changes

### Modified (1)

| Schema | Name | Body Changed |
|---|---|---|
| dbo | vw_StudentOverview | Yes |

---

## Foreign Key Changes

### Added (2)

| Constraint | Parent | Column | References |
|---|---|---|---|
| FK_Courses_Categories | Courses | CategoryId | CourseCategories.CategoryId |
| FK_StudentNotes_Students | StudentNotes | StudentId | Students.StudentId |

---

## Risk Assessment

| Change | Risk | Affected Objects | Details |
|---|---|---|---|
| Drop column `Students.LegacyCode` | CRITICAL | 3 objects | sp_SearchStudents, sp_MigrateLegacyCodes, vw_StudentOverview reference this column |
| Alter `Students.Email` type (nvarchar(100) -> nvarchar(255)) | HIGH | 2 objects | sp_GetStudentById, sp_SearchStudents use this column; possible index rebuild |
| Modify `sp_GetStudentById` | MEDIUM | 5 objects | Called by sp_EnrollStudent, sp_GenerateTranscript, and 3 other SPs |
| Modify `sp_SearchStudents` | MEDIUM | 2 objects | Called by sp_GetEnrollmentReport and 1 view |
| Modify `sp_EnrollStudent` | MEDIUM | 1 object | Called by sp_GetEnrollmentReport |
| Drop column `Enrollments.LegacyFlag` | LOW | 0 objects | No references found in SPs or views |
| Add table `CourseCategories` | NONE | 0 objects | New table with no existing dependencies |
| Add table `StudentNotes` | NONE | 0 objects | New table with no existing dependencies |

### Risk Summary

- **CRITICAL:** 1 change (requires manual review before deployment)
- **HIGH:** 1 change (automated migration possible with caution)
- **MEDIUM:** 3 changes (standard migration)
- **LOW:** 1 change (safe to automate)
- **NONE:** 2 changes (additive only)

---

## Recommendations

1. **Review CRITICAL changes manually** before running migration. Dropping `Students.LegacyCode` will break 2 stored procedures and 1 view.
2. **Update dependent SPs first** -- modify `sp_SearchStudents` and `sp_MigrateLegacyCodes` to remove references to `LegacyCode` before dropping the column.
3. **Update `vw_StudentOverview`** to remove `LegacyCode` reference before column drop.
4. **Test the 7 modified SPs** in a staging environment before deploying to production.
5. **Consider running during maintenance window** due to index changes on the `Students` table.

---

*Generated by [SQLForensic](https://github.com/mcandiri/sqlforensic)*
