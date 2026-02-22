-- ============================================================================
-- SQLForensic Migration Script
-- ============================================================================
-- Source (desired):  SchoolDB_Dev  @ dev-server
-- Target (current):  SchoolDB_Prod @ prod-server
-- Provider:          SQL Server
-- Generated:         2026-02-23T14:30:00
-- Overall Risk:      HIGH
-- Total Changes:     25
-- Safe Mode:         ON (IF EXISTS checks, transaction wrapping, rollback)
-- ============================================================================
--
-- IMPORTANT: Review all CRITICAL and HIGH risk sections before executing.
-- Lines marked with [MANUAL REVIEW] require human verification.
-- Commented-out DROP statements must be uncommented after dependent objects
-- have been updated.
--
-- Recommended execution order:
--   Step 1: Create new tables
--   Step 2: Add new columns to existing tables
--   Step 3: Modify existing columns
--   Step 4: Add new indexes
--   Step 5: Add new foreign keys
--   Step 6: Create/alter stored procedures
--   Step 7: Remove deprecated indexes
--   Step 8: Remove deprecated columns (CRITICAL - manual review required)
-- ============================================================================

SET XACT_ABORT ON;
SET NOCOUNT ON;
GO

BEGIN TRANSACTION;
GO

PRINT '=== SQLForensic Migration: SchoolDB_Dev -> SchoolDB_Prod ===';
PRINT 'Started at: ' + CONVERT(varchar, GETDATE(), 121);
GO

-- ============================================================================
-- STEP 1: Create New Tables
-- Risk: NONE (additive changes only)
-- ============================================================================

PRINT '-- Step 1: Creating new tables...';
GO

-- Table: dbo.CourseCategories
IF NOT EXISTS (
    SELECT 1 FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = 'CourseCategories'
)
BEGIN
    CREATE TABLE [dbo].[CourseCategories] (
        [CategoryId]   INT            NOT NULL IDENTITY(1,1),
        [CategoryName] NVARCHAR(100)  NOT NULL,
        [Description]  NVARCHAR(500)  NULL,
        [IsActive]     BIT            NOT NULL CONSTRAINT [DF_CourseCategories_IsActive] DEFAULT (1),
        [CreatedDate]  DATETIME2      NOT NULL CONSTRAINT [DF_CourseCategories_CreatedDate] DEFAULT (GETDATE()),
        [SortOrder]    INT            NOT NULL CONSTRAINT [DF_CourseCategories_SortOrder] DEFAULT (0),
        CONSTRAINT [PK_CourseCategories] PRIMARY KEY CLUSTERED ([CategoryId])
    );
    PRINT '  Created table: dbo.CourseCategories';
END
ELSE
    PRINT '  Skipped: dbo.CourseCategories already exists';
GO

-- Table: dbo.StudentNotes
IF NOT EXISTS (
    SELECT 1 FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = 'StudentNotes'
)
BEGIN
    CREATE TABLE [dbo].[StudentNotes] (
        [NoteId]          INT            NOT NULL IDENTITY(1,1),
        [StudentId]       INT            NOT NULL,
        [NoteType]        NVARCHAR(50)   NOT NULL CONSTRAINT [DF_StudentNotes_NoteType] DEFAULT ('General'),
        [NoteText]        NVARCHAR(MAX)  NOT NULL,
        [CreatedBy]       INT            NULL,
        [CreatedDate]     DATETIME2      NOT NULL CONSTRAINT [DF_StudentNotes_CreatedDate] DEFAULT (GETDATE()),
        [IsConfidential]  BIT            NOT NULL CONSTRAINT [DF_StudentNotes_IsConfidential] DEFAULT (0),
        CONSTRAINT [PK_StudentNotes] PRIMARY KEY CLUSTERED ([NoteId])
    );
    PRINT '  Created table: dbo.StudentNotes';
END
ELSE
    PRINT '  Skipped: dbo.StudentNotes already exists';
GO

-- ============================================================================
-- STEP 2: Add New Columns to Existing Tables
-- Risk: LOW (nullable columns with defaults)
-- ============================================================================

PRINT '-- Step 2: Adding new columns...';
GO

-- Table: dbo.Students - Add MiddleName
IF NOT EXISTS (
    SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = 'Students' AND COLUMN_NAME = 'MiddleName'
)
BEGIN
    ALTER TABLE [dbo].[Students] ADD [MiddleName] NVARCHAR(100) NULL;
    PRINT '  Added column: Students.MiddleName';
END
GO

-- Table: dbo.Students - Add PreferredName
IF NOT EXISTS (
    SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = 'Students' AND COLUMN_NAME = 'PreferredName'
)
BEGIN
    ALTER TABLE [dbo].[Students] ADD [PreferredName] NVARCHAR(100) NULL;
    PRINT '  Added column: Students.PreferredName';
END
GO

-- Table: dbo.Courses - Add CategoryId
IF NOT EXISTS (
    SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = 'Courses' AND COLUMN_NAME = 'CategoryId'
)
BEGIN
    ALTER TABLE [dbo].[Courses] ADD [CategoryId] INT NULL;
    PRINT '  Added column: Courses.CategoryId';
END
GO

-- Table: dbo.Courses - Add MaxCapacity
IF NOT EXISTS (
    SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = 'Courses' AND COLUMN_NAME = 'MaxCapacity'
)
BEGIN
    ALTER TABLE [dbo].[Courses] ADD [MaxCapacity] INT NOT NULL CONSTRAINT [DF_Courses_MaxCapacity] DEFAULT (30);
    PRINT '  Added column: Courses.MaxCapacity';
END
GO

-- ============================================================================
-- STEP 3: Modify Existing Columns
-- Risk: HIGH - Verify data compatibility before running
-- ============================================================================

PRINT '-- Step 3: Modifying existing columns...';
GO

-- [HIGH RISK] Students.Email: nvarchar(100) -> nvarchar(255)
-- Widening change - generally safe, but verify index impact.
-- Affected objects: sp_GetStudentById, sp_SearchStudents
IF EXISTS (
    SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = 'Students'
      AND COLUMN_NAME = 'Email' AND CHARACTER_MAXIMUM_LENGTH = 100
)
BEGIN
    -- Validate: check max actual length before widening
    DECLARE @maxEmailLen INT;
    SELECT @maxEmailLen = MAX(LEN([Email])) FROM [dbo].[Students];
    PRINT '  Students.Email max current length: ' + ISNULL(CAST(@maxEmailLen AS VARCHAR), '0');

    ALTER TABLE [dbo].[Students] ALTER COLUMN [Email] NVARCHAR(255);
    PRINT '  Modified column: Students.Email (nvarchar(100) -> nvarchar(255))';
END
GO

-- Students.Phone: NOT NULL -> NULL
IF EXISTS (
    SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = 'Students'
      AND COLUMN_NAME = 'Phone' AND IS_NULLABLE = 'NO'
)
BEGIN
    ALTER TABLE [dbo].[Students] ALTER COLUMN [Phone] NVARCHAR(20) NULL;
    PRINT '  Modified column: Students.Phone (NOT NULL -> NULL)';
END
GO

-- Courses.CourseName: nvarchar(100) -> nvarchar(200)
IF EXISTS (
    SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = 'Courses'
      AND COLUMN_NAME = 'CourseName' AND CHARACTER_MAXIMUM_LENGTH = 100
)
BEGIN
    ALTER TABLE [dbo].[Courses] ALTER COLUMN [CourseName] NVARCHAR(200) NOT NULL;
    PRINT '  Modified column: Courses.CourseName (nvarchar(100) -> nvarchar(200))';
END
GO

-- Enrollments.Grade: decimal(3,1) -> decimal(5,2)
IF EXISTS (
    SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = 'Enrollments'
      AND COLUMN_NAME = 'Grade' AND NUMERIC_PRECISION = 3
)
BEGIN
    ALTER TABLE [dbo].[Enrollments] ALTER COLUMN [Grade] DECIMAL(5,2) NULL;
    PRINT '  Modified column: Enrollments.Grade (decimal(3,1) -> decimal(5,2))';
END
GO

-- Enrollments.Status: default change ('Active' -> 'Pending')
-- Drop old default constraint and create new one
IF EXISTS (
    SELECT dc.name
    FROM sys.default_constraints dc
    JOIN sys.columns c ON dc.parent_object_id = c.object_id AND dc.parent_column_id = c.column_id
    WHERE OBJECT_NAME(dc.parent_object_id) = 'Enrollments' AND c.name = 'Status'
)
BEGIN
    DECLARE @dfName NVARCHAR(256);
    SELECT @dfName = dc.name
    FROM sys.default_constraints dc
    JOIN sys.columns c ON dc.parent_object_id = c.object_id AND dc.parent_column_id = c.column_id
    WHERE OBJECT_NAME(dc.parent_object_id) = 'Enrollments' AND c.name = 'Status';

    EXEC('ALTER TABLE [dbo].[Enrollments] DROP CONSTRAINT [' + @dfName + ']');
    ALTER TABLE [dbo].[Enrollments] ADD CONSTRAINT [DF_Enrollments_Status] DEFAULT ('Pending') FOR [Status];
    PRINT '  Modified default: Enrollments.Status (''Active'' -> ''Pending'')';
END
GO

-- ============================================================================
-- STEP 4: Add New Indexes
-- Risk: LOW (additive, but may cause brief locking on large tables)
-- ============================================================================

PRINT '-- Step 4: Adding new indexes...';
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'IX_Students_Email' AND object_id = OBJECT_ID('dbo.Students')
)
BEGIN
    CREATE NONCLUSTERED INDEX [IX_Students_Email]
    ON [dbo].[Students] ([Email]);
    PRINT '  Created index: IX_Students_Email';
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'IX_Students_PreferredName' AND object_id = OBJECT_ID('dbo.Students')
)
BEGIN
    CREATE NONCLUSTERED INDEX [IX_Students_PreferredName]
    ON [dbo].[Students] ([PreferredName]);
    PRINT '  Created index: IX_Students_PreferredName';
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'IX_Courses_CategoryId' AND object_id = OBJECT_ID('dbo.Courses')
)
BEGIN
    CREATE NONCLUSTERED INDEX [IX_Courses_CategoryId]
    ON [dbo].[Courses] ([CategoryId]);
    PRINT '  Created index: IX_Courses_CategoryId';
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'IX_Enrollments_Status' AND object_id = OBJECT_ID('dbo.Enrollments')
)
BEGIN
    CREATE NONCLUSTERED INDEX [IX_Enrollments_Status]
    ON [dbo].[Enrollments] ([Status]);
    PRINT '  Created index: IX_Enrollments_Status';
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'IX_StudentNotes_StudentId' AND object_id = OBJECT_ID('dbo.StudentNotes')
)
BEGIN
    CREATE NONCLUSTERED INDEX [IX_StudentNotes_StudentId]
    ON [dbo].[StudentNotes] ([StudentId], [CreatedDate] DESC);
    PRINT '  Created index: IX_StudentNotes_StudentId';
END
GO

-- ============================================================================
-- STEP 5: Add New Foreign Keys
-- Risk: LOW (ensure referenced data exists first)
-- ============================================================================

PRINT '-- Step 5: Adding foreign keys...';
GO

-- FK: Courses.CategoryId -> CourseCategories.CategoryId
IF NOT EXISTS (
    SELECT 1 FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS
    WHERE CONSTRAINT_NAME = 'FK_Courses_Categories'
)
BEGIN
    -- Validate: ensure no orphan rows before adding FK
    IF NOT EXISTS (
        SELECT 1 FROM [dbo].[Courses] c
        WHERE c.[CategoryId] IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM [dbo].[CourseCategories] cc WHERE cc.[CategoryId] = c.[CategoryId])
    )
    BEGIN
        ALTER TABLE [dbo].[Courses]
        ADD CONSTRAINT [FK_Courses_Categories]
        FOREIGN KEY ([CategoryId]) REFERENCES [dbo].[CourseCategories] ([CategoryId]);
        PRINT '  Added FK: FK_Courses_Categories';
    END
    ELSE
    BEGIN
        PRINT '  WARNING: Orphan rows found in Courses.CategoryId - FK not created';
        PRINT '  [MANUAL REVIEW] Fix orphan data before adding FK_Courses_Categories';
    END
END
GO

-- FK: StudentNotes.StudentId -> Students.StudentId
IF NOT EXISTS (
    SELECT 1 FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS
    WHERE CONSTRAINT_NAME = 'FK_StudentNotes_Students'
)
BEGIN
    ALTER TABLE [dbo].[StudentNotes]
    ADD CONSTRAINT [FK_StudentNotes_Students]
    FOREIGN KEY ([StudentId]) REFERENCES [dbo].[Students] ([StudentId]);
    PRINT '  Added FK: FK_StudentNotes_Students';
END
GO

-- ============================================================================
-- STEP 6: Create / Alter Stored Procedures & Views
-- Risk: MEDIUM (verify logic changes in staging first)
-- ============================================================================

PRINT '-- Step 6: Updating stored procedures and views...';
PRINT '  [MANUAL REVIEW] The following objects have changed definitions.';
PRINT '  SQLForensic detected body changes but cannot auto-generate SP code.';
PRINT '  Deploy updated SP definitions from your source database or version control.';
GO

-- New SPs to create (deploy from source):
--   dbo.sp_GetStudentNotes
--   dbo.sp_AddStudentNote
--   dbo.sp_GetCoursesByCategory
--   dbo.sp_UpdateStudentPreferences

-- Modified SPs to update (deploy from source):
--   dbo.sp_GetStudentById
--   dbo.sp_SearchStudents
--   dbo.sp_EnrollStudent
--   dbo.sp_GetEnrollmentReport
--   dbo.sp_UpdateStudentProfile
--   dbo.sp_GetCourseRoster
--   dbo.sp_GenerateTranscript

-- Modified Views to update (deploy from source):
--   dbo.vw_StudentOverview
--   WARNING: vw_StudentOverview references Students.LegacyCode which is
--   scheduled for removal in Step 8. Update this view BEFORE dropping the column.

-- Removed SP (safe to drop after verifying no external callers):
-- IF EXISTS (SELECT 1 FROM sys.objects WHERE name = 'sp_MigrateLegacyCodes' AND type = 'P')
-- BEGIN
--     DROP PROCEDURE [dbo].[sp_MigrateLegacyCodes];
--     PRINT '  Dropped SP: sp_MigrateLegacyCodes';
-- END
-- GO

-- ============================================================================
-- STEP 7: Remove Deprecated Indexes
-- Risk: LOW (index was on column being dropped)
-- ============================================================================

PRINT '-- Step 7: Removing deprecated indexes...';
GO

IF EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'IX_Students_LegacyCode' AND object_id = OBJECT_ID('dbo.Students')
)
BEGIN
    DROP INDEX [IX_Students_LegacyCode] ON [dbo].[Students];
    PRINT '  Dropped index: IX_Students_LegacyCode';
END
GO

-- ============================================================================
-- STEP 8: Remove Deprecated Columns
-- Risk: CRITICAL - These columns are referenced by existing objects
-- ============================================================================

PRINT '-- Step 8: Removing deprecated columns...';
PRINT '  [MANUAL REVIEW] CRITICAL changes below are commented out.';
PRINT '  Uncomment ONLY after updating all dependent objects.';
GO

-- !! CRITICAL !! Students.LegacyCode
-- Referenced by:
--   - dbo.sp_SearchStudents (SELECT, WHERE clause)
--   - dbo.sp_MigrateLegacyCodes (UPDATE, WHERE clause)
--   - dbo.vw_StudentOverview (SELECT)
--
-- Before uncommenting:
--   1. Deploy updated sp_SearchStudents (without LegacyCode reference)
--   2. Drop or update sp_MigrateLegacyCodes
--   3. Deploy updated vw_StudentOverview (without LegacyCode reference)
--   4. Verify no external applications reference this column
--
-- IF EXISTS (
--     SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
--     WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = 'Students' AND COLUMN_NAME = 'LegacyCode'
-- )
-- BEGIN
--     -- Back up data before dropping (optional safety measure)
--     -- SELECT StudentId, LegacyCode INTO dbo.Students_LegacyCode_Backup FROM dbo.Students WHERE LegacyCode IS NOT NULL;
--     ALTER TABLE [dbo].[Students] DROP COLUMN [LegacyCode];
--     PRINT '  Dropped column: Students.LegacyCode';
-- END
-- GO

-- Enrollments.LegacyFlag (LOW risk - no references found)
IF EXISTS (
    SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = 'Enrollments' AND COLUMN_NAME = 'LegacyFlag'
)
BEGIN
    ALTER TABLE [dbo].[Enrollments] DROP COLUMN [LegacyFlag];
    PRINT '  Dropped column: Enrollments.LegacyFlag';
END
GO

-- ============================================================================
-- COMPLETION
-- ============================================================================

PRINT '';
PRINT '=== Migration Complete ===';
PRINT 'Finished at: ' + CONVERT(varchar, GETDATE(), 121);
PRINT '';
PRINT 'Post-migration checklist:';
PRINT '  [ ] Verify all new tables created correctly';
PRINT '  [ ] Deploy updated stored procedures from source (Step 6)';
PRINT '  [ ] Update vw_StudentOverview to remove LegacyCode reference';
PRINT '  [ ] Uncomment Students.LegacyCode drop after dependent objects updated';
PRINT '  [ ] Run application integration tests';
PRINT '  [ ] Verify foreign key constraints with production data';
GO

COMMIT TRANSACTION;
GO

-- ============================================================================
-- ROLLBACK SCRIPT (in case of failure)
-- ============================================================================
-- To undo this migration, run the following in reverse order:
--
-- -- Re-add dropped columns
-- ALTER TABLE [dbo].[Enrollments] ADD [LegacyFlag] BIT NOT NULL DEFAULT (0);
--
-- -- Drop new indexes
-- DROP INDEX IF EXISTS [IX_Students_Email] ON [dbo].[Students];
-- DROP INDEX IF EXISTS [IX_Students_PreferredName] ON [dbo].[Students];
-- DROP INDEX IF EXISTS [IX_Courses_CategoryId] ON [dbo].[Courses];
-- DROP INDEX IF EXISTS [IX_Enrollments_Status] ON [dbo].[Enrollments];
-- DROP INDEX IF EXISTS [IX_StudentNotes_StudentId] ON [dbo].[StudentNotes];
--
-- -- Re-add removed index
-- CREATE NONCLUSTERED INDEX [IX_Students_LegacyCode] ON [dbo].[Students] ([LegacyCode]);
--
-- -- Drop foreign keys
-- ALTER TABLE [dbo].[Courses] DROP CONSTRAINT IF EXISTS [FK_Courses_Categories];
-- ALTER TABLE [dbo].[StudentNotes] DROP CONSTRAINT IF EXISTS [FK_StudentNotes_Students];
--
-- -- Revert column modifications
-- ALTER TABLE [dbo].[Students] ALTER COLUMN [Email] NVARCHAR(100);
-- ALTER TABLE [dbo].[Students] ALTER COLUMN [Phone] NVARCHAR(20) NOT NULL;
-- ALTER TABLE [dbo].[Courses] ALTER COLUMN [CourseName] NVARCHAR(100) NOT NULL;
-- ALTER TABLE [dbo].[Enrollments] ALTER COLUMN [Grade] DECIMAL(3,1) NULL;
--
-- -- Drop added columns
-- ALTER TABLE [dbo].[Students] DROP COLUMN [MiddleName];
-- ALTER TABLE [dbo].[Students] DROP COLUMN [PreferredName];
-- ALTER TABLE [dbo].[Courses] DROP COLUMN [CategoryId];
-- ALTER TABLE [dbo].[Courses] DROP COLUMN [MaxCapacity];
--
-- -- Drop new tables
-- DROP TABLE IF EXISTS [dbo].[StudentNotes];
-- DROP TABLE IF EXISTS [dbo].[CourseCategories];
-- ============================================================================
-- Generated by SQLForensic (https://github.com/mcandiri/sqlforensic)
-- ============================================================================
