# Composition Index & Lazy Loading Design

## Core Principles

1. **Index Everything, Cache Nothing Initially**
   - Scan all composition directories and build searchable metadata index
   - Only load actual compositions when requested
   - SQLite-backed index for fast queries

2. **External Repository Support**
   - Support multiple composition sources (local, git repos, URLs)
   - Repository metadata separate from composition metadata
   - Lazy clone/sync external repositories

3. **LRU Memory Cache**
   - Small in-memory cache (e.g., 50 compositions max)
   - Recently used compositions stay hot
   - Cache misses trigger lazy load from disk

## Database Schema

```sql
-- Composition repositories
CREATE TABLE composition_repositories (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL, -- 'local', 'git', 'url'
    path TEXT NOT NULL, -- file path or URL
    status TEXT NOT NULL, -- 'active', 'syncing', 'error'
    last_sync_at TEXT,
    metadata TEXT -- JSON: branch, credentials, etc.
);

-- Composition index
CREATE TABLE composition_index (
    full_name TEXT PRIMARY KEY, -- repo_id:name or just name for local
    name TEXT NOT NULL,
    type TEXT NOT NULL, -- profile, prompt, orchestration
    repository_id TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_hash TEXT, -- for change detection
    version TEXT,
    description TEXT,
    author TEXT,
    tags TEXT, -- JSON array
    capabilities TEXT, -- JSON array
    dependencies TEXT, -- JSON array: [repo:name, name]
    permissions TEXT, -- JSON: creation/modification rules
    mutable BOOLEAN DEFAULT FALSE,
    ephemeral BOOLEAN DEFAULT FALSE,
    indexed_at TEXT NOT NULL,
    FOREIGN KEY (repository_id) REFERENCES composition_repositories(id)
);

-- Optimized indexes
CREATE INDEX idx_comp_type ON composition_index(type);
CREATE INDEX idx_comp_repo ON composition_index(repository_id);
CREATE INDEX idx_comp_tags ON composition_index(tags);
CREATE INDEX idx_comp_caps ON composition_index(capabilities);
CREATE INDEX idx_comp_deps ON composition_index(dependencies);
CREATE INDEX idx_comp_hash ON composition_index(file_hash);
```

## Implementation Strategy

```python
class CompositionIndexManager(BaseManager):
    """SQLite-backed composition index with lazy loading"""
    
    def __init__(self):
        super().__init__(manager_name="composition_index")
        self.memory_cache = LRUCache(maxsize=50)  # Small hot cache
        
    async def discover_compositions(self, query: CompositionQuery):
        """Fast metadata-only search"""
        # Query index table only - no file I/O
        sql = """
        SELECT full_name, name, type, description, tags, capabilities
        FROM composition_index 
        WHERE type = ? 
        AND (tags LIKE ? OR capabilities LIKE ?)
        ORDER BY name
        """
        # Return lightweight metadata, not full compositions
        
    async def load_composition(self, full_name: str):
        """Lazy load composition on demand"""
        # Check memory cache first
        if full_name in self.memory_cache:
            return self.memory_cache[full_name]
            
        # Get file path from index
        row = await self.get_index_entry(full_name)
        
        # Load from disk only when needed
        composition = await self.load_from_file(row.file_path)
        
        # Cache in memory for future use
        self.memory_cache[full_name] = composition
        return composition
        
    async def sync_repositories(self):
        """Background sync of external repositories"""
        for repo in await self.get_repositories():
            if repo.type == 'git':
                await self.sync_git_repo(repo)
            elif repo.type == 'url':
                await self.sync_url_repo(repo)
                
    async def rebuild_index(self, repo_id: Optional[str] = None):
        """Rebuild index from file system"""
        repos = [repo_id] if repo_id else await self.get_all_repo_ids()
        
        for repo_id in repos:
            repo = await self.get_repository(repo_id)
            async for file_path in self.scan_compositions(repo.path):
                await self.index_composition_file(repo_id, file_path)
```

## External Repository Examples

```yaml
# Repository configuration
repositories:
  - id: "local"
    type: "local" 
    path: "var/lib/compositions"
    
  - id: "ksi_community"
    type: "git"
    path: "https://github.com/ksi-community/compositions.git"
    branch: "main"
    
  - id: "team_drafts"
    type: "git"
    path: "git@company:team/ai-compositions.git"
    branch: "develop"
    
  - id: "research_lab"
    type: "url"
    path: "https://lab.example.com/compositions/"
    index_url: "https://lab.example.com/compositions/index.json"
```

## Usage Patterns

```python
# Fast discovery (index-only, no file loading)
discoveries = await composition_service.discover({
    "type": "profile",
    "capabilities": ["coding", "debugging"],
    "repositories": ["local", "ksi_community"]
})
# Returns: [{"full_name": "local:researcher", "name": "researcher", ...}]

# Lazy loading when actually needed
profile = await composition_service.load("ksi_community:advanced_researcher")
# Only NOW does it load the YAML file

# Repository management
await composition_service.sync_repository("ksi_community")
await composition_service.add_repository({
    "id": "new_repo",
    "type": "git", 
    "path": "https://github.com/new/repo.git"
})
```

## Events

```python
# Index management
"composition:index:rebuild"   # Rebuild index from files
"composition:index:sync"      # Sync external repositories
"composition:repo:add"        # Add new repository
"composition:repo:remove"     # Remove repository

# Discovery (fast, index-only)
"composition:discover"        # Search index
"composition:list"           # List by type/repo

# Loading (lazy, on-demand)
"composition:load"           # Load specific composition
"composition:resolve"        # Load and resolve variables
```

This approach gives us:

1. **Instant discovery** - SQLite index queries are fast even with thousands of compositions
2. **Minimal memory usage** - Only cache what's actually used
3. **External repository support** - Git repos, URLs, etc.
4. **Change detection** - File hashes detect updates
5. **Repository isolation** - Clear namespacing (repo:name)

The key insight: **metadata is cheap, content is expensive**. We index all the metadata but only load content when needed.

What do you think? Should we also add dependency resolution to the index for detecting circular dependencies without loading files?