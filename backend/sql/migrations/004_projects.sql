CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(id),
    user_id TEXT NOT NULL REFERENCES users(id),
    title TEXT NOT NULL DEFAULT '새 프로젝트',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_projects_owner ON projects(tenant_id, user_id, updated_at DESC);

-- Existing chats and their Stage data are grouped under one per-user default project.
INSERT INTO projects (id, tenant_id, user_id, title)
SELECT 'prj_default_' || id, tenant_id, id, '디폴트'
FROM users
ON CONFLICT (id) DO NOTHING;

ALTER TABLE conversations
    ADD COLUMN IF NOT EXISTS project_id TEXT REFERENCES projects(id) ON DELETE RESTRICT;

UPDATE conversations
SET project_id = 'prj_default_' || user_id
WHERE project_id IS NULL;

ALTER TABLE conversations
    ALTER COLUMN project_id SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_conversations_project
    ON conversations(project_id, updated_at DESC);

ALTER TABLE stages
    ADD COLUMN IF NOT EXISTS project_id TEXT REFERENCES projects(id) ON DELETE CASCADE;

UPDATE stages AS s
SET project_id = c.project_id
FROM conversations AS c
WHERE c.id = s.conversation_id
  AND s.project_id IS NULL;

-- Retain existing widgets while merging each user's former chat stages into one project Stage.
WITH ranked_stages AS (
    SELECT
        id,
        project_id,
        first_value(id) OVER (
            PARTITION BY project_id
            ORDER BY created_at ASC, id ASC
        ) AS target_stage_id,
        row_number() OVER (
            PARTITION BY project_id
            ORDER BY created_at ASC, id ASC
        ) - 1 AS stage_position
    FROM stages
)
UPDATE stage_widgets AS w
SET
    stage_id = ranked_stages.target_stage_id,
    layout_y = w.layout_y + (ranked_stages.stage_position * 1000)
FROM ranked_stages
WHERE w.stage_id = ranked_stages.id;

WITH ranked_stages AS (
    SELECT
        id,
        first_value(id) OVER (
            PARTITION BY project_id
            ORDER BY created_at ASC, id ASC
        ) AS target_stage_id
    FROM stages
)
DELETE FROM stages AS s
USING ranked_stages
WHERE s.id = ranked_stages.id
  AND ranked_stages.id <> ranked_stages.target_stage_id;

ALTER TABLE stages DROP CONSTRAINT IF EXISTS stages_conversation_id_key;
ALTER TABLE stages DROP COLUMN IF EXISTS conversation_id;
ALTER TABLE stages ALTER COLUMN project_id SET NOT NULL;
ALTER TABLE stages ADD CONSTRAINT stages_project_id_key UNIQUE (project_id);
