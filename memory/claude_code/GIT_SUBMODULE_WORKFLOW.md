# Git Submodule Workflow for KSI

This document describes the workflow for working with KSI's federated git submodule architecture.

## Overview

KSI uses git submodules to manage components in separate repositories:
- **compositions**: https://github.com/durapensa/ksi-compositions
- **evaluations**: https://github.com/durapensa/ksi-evaluations  
- **capabilities**: https://github.com/durapensa/ksi-capabilities

## Initial Setup

### Cloning KSI with Submodules

```bash
# Clone with submodules
git clone --recursive https://github.com/durapensa/ksi.git

# Or if already cloned without submodules
git submodule update --init --recursive
```

## Working with Submodules

### Making Changes in a Submodule

1. **Navigate to the submodule**:
   ```bash
   cd var/lib/compositions
   ```

2. **Make your changes** (KSI automatically commits most operations)

3. **Check status**:
   ```bash
   git status
   ```

4. **Commit any manual changes**:
   ```bash
   git add .
   git commit -m "feat: Add new composition"
   ```

5. **Push to submodule's GitHub**:
   ```bash
   git push origin main
   ```

### Updating Parent Repository

After pushing submodule changes, the parent repo needs to track the new commits:

1. **Return to parent repo root**:
   ```bash
   cd /path/to/ksi
   ```

2. **Stage submodule updates**:
   ```bash
   git add var/lib/compositions var/lib/evaluations var/lib/capabilities
   ```

3. **Commit the reference updates**:
   ```bash
   git commit -m "chore: Update submodule references"
   ```

## KSI-Specific Features

### Automatic Git Commits

KSI automatically creates git commits for:
- `composition:save` - Saves with descriptive commit message
- `composition:fork` - Tracks lineage in commit and metadata
- Similar operations in evaluations and capabilities

### Checking Repository Status

```bash
# Through KSI
./ksi send composition:git_info

# Or directly
cd var/lib/compositions && git status
```

### Syncing Submodules

```bash
# Through KSI (pulls latest from remotes)
./ksi send composition:sync

# Or manually
git submodule update --remote --merge
```

## Common Tasks

### Update All Submodules to Latest

```bash
git submodule foreach git pull origin main
git add var/lib/*
git commit -m "chore: Update all submodules to latest"
```

### Check Which Submodules Have Changes

```bash
git status  # Shows modified submodules
git submodule status  # Shows commit hashes
```

### See What Changed in a Submodule

```bash
cd var/lib/compositions
git log --oneline origin/main..HEAD  # Shows unpushed commits
git diff origin/main  # Shows unpushed changes
```

## Best Practices

1. **Always push submodule changes first** before updating parent repo
2. **Use descriptive commit messages** in both submodules and parent
3. **Keep submodules synchronized** - don't let them diverge too far
4. **Test before pushing** - ensure compositions/evaluations work
5. **Document breaking changes** in both submodule and parent repos

## Troubleshooting

### Submodule is in detached HEAD state

```bash
cd var/lib/compositions
git checkout main
git pull origin main
```

### Parent repo shows modified submodules after pull

```bash
git submodule update --init --recursive
```

### Merge conflicts in submodules

```bash
cd var/lib/compositions
git fetch origin
git merge origin/main
# Resolve conflicts
git add .
git commit
```

## Architecture Benefits

- **Independent Development**: Each component type can evolve separately
- **Version Control**: Complete history for all components
- **Collaboration**: Multiple teams can work on different components
- **Rollback**: Easy to revert to previous versions
- **Federation**: Components can be shared across KSI instances