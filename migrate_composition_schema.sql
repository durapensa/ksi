-- Migration script to update composition_index schema
-- Changes 'type' column to 'component_type'

-- Create new table with updated schema
CREATE TABLE composition_index_new (
    full_name TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    component_type TEXT NOT NULL,  -- Changed from 'type'
    repository_id TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_hash TEXT,
    file_size INTEGER,
    version TEXT,
    description TEXT,
    author TEXT,
    timestamp TEXT,
    dependencies TEXT,
    metadata TEXT,
    git_info TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Copy data from old table
INSERT INTO composition_index_new (
    full_name, name, component_type, repository_id, file_path,
    file_hash, file_size, version, description, author,
    timestamp, dependencies, metadata, git_info, created_at, updated_at
)
SELECT 
    full_name, name, type, repository_id, file_path,
    file_hash, file_size, version, description, author,
    timestamp, dependencies, metadata, git_info, created_at, updated_at
FROM composition_index;

-- Drop old table
DROP TABLE composition_index;

-- Rename new table
ALTER TABLE composition_index_new RENAME TO composition_index;

-- Recreate indexes
CREATE INDEX idx_composition_type ON composition_index(component_type);
CREATE INDEX idx_composition_name ON composition_index(name);
CREATE INDEX idx_composition_repo ON composition_index(repository_id);
CREATE INDEX idx_composition_hash ON composition_index(file_hash);

-- Update any views or triggers if they exist
-- (None found in current schema)