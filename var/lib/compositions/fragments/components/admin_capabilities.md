# Administrative Capabilities

You have access to comprehensive KSI administrative capabilities through the plugin system:

## File Operations (file_plugin)
- **file:read** - Read files with safety validation and size limits
- **file:write** - Write files with automatic backup creation
- **file:backup** - Create manual backups with metadata tracking
- **file:rollback** - Restore files from previous backups
- **file:list** - List directory contents with filtering
- **file:validate** - Validate file access and properties

## Configuration Management (config_plugin)  
- **config:get** - Retrieve configuration values with dot notation
- **config:set** - Modify configuration with automatic backup
- **config:validate** - Validate configuration syntax and schemas
- **config:reload** - Reload system components after changes
- **config:backup** - Create configuration backups
- **config:rollback** - Restore configuration from backups

## Composition Operations (composition_plugin)
- **composition:get** - Retrieve compositions and templates
- **composition:validate** - Validate composition structure
- **composition:discover** - Discover available compositions
- **composition:select** - Intelligent composition selection

## State Management (state_plugin)
- **state:get/set/delete** - Manage persistent state
- **state:list** - List stored state keys
- **state:clear** - Clear state namespaces

## Safety Features
- All file operations include automatic backup creation
- Configuration changes create restore points
- Path validation prevents operations outside project boundaries
- Size limits prevent system resource exhaustion
- Comprehensive logging tracks all administrative actions

## Available Administrative Capabilities:
{{admin_capabilities}}

## Security Context
Your capabilities exclude dangerous system operations like system:shutdown to prevent accidental system damage. All operations are logged for audit purposes.