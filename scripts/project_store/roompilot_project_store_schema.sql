-- RoomPilot Phase 3 project/workflow persistence schema.
-- Binary uploads and PNG renders remain under .runtime; PostgreSQL stores
-- canonical JSONB state, revision control and file metadata.
-- Keep this schema beside migrate_sqlite_projects_to_postgres.py.

CREATE SCHEMA IF NOT EXISTS roompilot;

CREATE TABLE IF NOT EXISTS roompilot.projects (
    project_id       TEXT PRIMARY KEY,
    name             TEXT NOT NULL,
    notes            TEXT NOT NULL DEFAULT '',
    current_step     VARCHAR(50) NOT NULL,
    workflow_json    JSONB NOT NULL DEFAULT '{}'::JSONB,
    revision         INTEGER NOT NULL DEFAULT 0,
    upload_filename  TEXT,
    upload_extension VARCHAR(20),
    upload_mime      VARCHAR(100),
    upload_path      TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT projects_revision_nonnegative CHECK (revision >= 0),
    CONSTRAINT projects_workflow_object CHECK (JSONB_TYPEOF(workflow_json) = 'object'),
    CONSTRAINT projects_upload_metadata_complete CHECK (
        (upload_path IS NULL AND upload_filename IS NULL
            AND upload_extension IS NULL AND upload_mime IS NULL)
        OR
        (upload_path IS NOT NULL AND upload_filename IS NOT NULL
            AND upload_extension IS NOT NULL AND upload_mime IS NOT NULL)
    )
);

CREATE TABLE IF NOT EXISTS roompilot.render_outputs (
    render_id          TEXT PRIMARY KEY,
    project_id         TEXT NOT NULL
                       REFERENCES roompilot.projects(project_id) ON DELETE CASCADE,
    white_model_version INTEGER NOT NULL,
    viewpoint_version   INTEGER NOT NULL,
    style_version       INTEGER NOT NULL,
    style_card_id       TEXT NOT NULL,
    provider            VARCHAR(100) NOT NULL,
    mime_type           VARCHAR(100) NOT NULL,
    filename            TEXT NOT NULL,
    file_path           TEXT NOT NULL,
    byte_size           BIGINT NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT render_white_model_version_nonnegative
        CHECK (white_model_version >= 0),
    CONSTRAINT render_viewpoint_version_nonnegative
        CHECK (viewpoint_version >= 0),
    CONSTRAINT render_style_version_nonnegative
        CHECK (style_version >= 0),
    CONSTRAINT render_byte_size_nonnegative CHECK (byte_size >= 0)
);

-- Designer-confirmed engineering snapshots are immutable inputs for all
-- estimate/report documents. design_revision is intentionally separate from
-- projects.revision, which remains the optimistic-concurrency counter.
CREATE TABLE IF NOT EXISTS roompilot.engineering_snapshots (
    project_id              TEXT NOT NULL
                            REFERENCES roompilot.projects(project_id) ON DELETE CASCADE,
    design_revision         VARCHAR(80) NOT NULL,
    source_project_revision INTEGER NOT NULL,
    snapshot_json           JSONB NOT NULL,
    approval_status         VARCHAR(30) NOT NULL DEFAULT 'draft',
    locked_by               TEXT,
    locked_at               TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (project_id, design_revision),
    CONSTRAINT engineering_snapshot_source_revision_nonnegative
        CHECK (source_project_revision >= 0),
    CONSTRAINT engineering_snapshot_json_object
        CHECK (JSONB_TYPEOF(snapshot_json) = 'object'),
    CONSTRAINT engineering_snapshot_approval
        CHECK (approval_status IN ('draft', 'designer_confirmed')),
    CONSTRAINT engineering_snapshot_lock_complete CHECK (
        (approval_status = 'draft' AND locked_by IS NULL AND locked_at IS NULL)
        OR
        (approval_status = 'designer_confirmed' AND locked_by IS NOT NULL AND locked_at IS NOT NULL)
    )
);

CREATE TABLE IF NOT EXISTS roompilot.engineering_jobs (
    job_id          TEXT PRIMARY KEY,
    project_id      TEXT NOT NULL
                    REFERENCES roompilot.projects(project_id) ON DELETE CASCADE,
    design_revision VARCHAR(80) NOT NULL,
    job_json        JSONB NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT engineering_job_json_object CHECK (JSONB_TYPEOF(job_json) = 'object')
);

CREATE TABLE IF NOT EXISTS roompilot.engineering_packages (
    package_id      TEXT PRIMARY KEY,
    project_id      TEXT NOT NULL
                    REFERENCES roompilot.projects(project_id) ON DELETE CASCADE,
    design_revision VARCHAR(80) NOT NULL,
    snapshot_hash   CHAR(64) NOT NULL,
    report_json     JSONB NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT engineering_package_hash_format
        CHECK (snapshot_hash ~ '^[0-9a-f]{64}$'),
    CONSTRAINT engineering_report_json_object
        CHECK (JSONB_TYPEOF(report_json) = 'object')
);

CREATE TABLE IF NOT EXISTS roompilot.engineering_documents (
    document_id   TEXT PRIMARY KEY,
    package_id    TEXT NOT NULL
                  REFERENCES roompilot.engineering_packages(package_id) ON DELETE CASCADE,
    document_type VARCHAR(30) NOT NULL,
    file_name     TEXT NOT NULL,
    content_type  VARCHAR(150) NOT NULL,
    file_path     TEXT NOT NULL,
    byte_size     BIGINT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT engineering_document_type CHECK (
        document_type IN ('report_json', 'report_html', 'estimate_xlsx')
    ),
    CONSTRAINT engineering_document_size_nonnegative CHECK (byte_size >= 0)
);

CREATE INDEX IF NOT EXISTS idx_projects_updated_at
    ON roompilot.projects(updated_at DESC, project_id);

CREATE INDEX IF NOT EXISTS idx_render_outputs_project_created
    ON roompilot.render_outputs(project_id, created_at DESC, render_id DESC);

CREATE INDEX IF NOT EXISTS idx_engineering_jobs_project_revision
    ON roompilot.engineering_jobs(project_id, design_revision, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_engineering_packages_project_revision
    ON roompilot.engineering_packages(project_id, design_revision, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_engineering_documents_package
    ON roompilot.engineering_documents(package_id, created_at, document_id);
