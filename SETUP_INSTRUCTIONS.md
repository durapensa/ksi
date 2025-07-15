# KSI Git Submodule Setup Instructions

## Overview

This document provides step-by-step instructions for setting up the KSI git submodule architecture with GitHub repositories.

## Prerequisites

1. **GitHub CLI (gh)** - Install from https://cli.github.com/
2. **Git** - Standard git installation
3. **GitHub account** - With repository creation permissions

## Setup Process

### Step 1: Verify Prerequisites

```bash
# Check if gh CLI is installed
gh --version

# Check if authenticated
gh auth status

# If not authenticated, login
gh auth login
```

### Step 2: Run Repository Setup

```bash
# Execute the setup script
python setup_repositories.py
```

This will:
- Create the repository structure in `ksi_repositories/`
- Migrate existing `var/lib/` content
- Initialize git repositories
- Create setup scripts

### Step 3: Create GitHub Repositories

```bash
# Run the GitHub creation script
./create_github_repos.sh
```

This will:
- Create three public repositories on GitHub
- Add remote origins
- Push initial content

### Step 4: Set Up Submodules

```bash
# Run the submodule setup script
./setup_submodules.sh
```

This will:
- Remove existing `var/lib/` (backed up to `var/lib.backup`)
- Add the three repositories as submodules
- Update `.gitmodules` with correct URLs
- Initialize and update submodules

### Step 5: Test Integration

```bash
# Run the integration test
python test_git_integration.py
```

This will verify:
- Repository access and information
- Component save operations with git commits
- Fork operations with git lineage
- Submodule synchronization

## Repository Structure

After setup, you'll have:

```
ksi_repositories/
├── ksi-compositions/
│   ├── profiles/
│   ├── orchestrations/
│   ├── prompts/
│   ├── fragments/
│   └── patterns/
├── ksi-evaluations/
│   ├── test_suites/
│   ├── results/
│   ├── judge_bootstrap/
│   └── schemas/
└── ksi-capabilities/
    ├── schemas/
    ├── plugins/
    └── permissions/
```

## Main KSI Repository

After submodule setup:

```
var/lib/
├── compositions/     # -> GitHub submodule
├── evaluations/      # -> GitHub submodule
└── capabilities/     # -> GitHub submodule
```

## Troubleshooting

### Authentication Issues

```bash
# Re-authenticate with GitHub
gh auth logout
gh auth login
```

### Repository Creation Errors

```bash
# Check if repository already exists
gh repo view ksi-compositions

# Delete if needed (careful!)
gh repo delete ksi-compositions --confirm
```

### Submodule Issues

```bash
# Reset submodules
git submodule deinit --all
rm -rf .git/modules/var/lib/*
git rm -rf var/lib

# Re-run setup
./setup_submodules.sh
```

### Content Migration Issues

```bash
# Check if var/lib exists
ls -la var/lib

# If missing, check backup
ls -la var/lib.backup

# Restore if needed
mv var/lib.backup var/lib
```

## Manual Setup (Alternative)

If the scripts don't work, you can set up manually:

### 1. Create Repositories

```bash
# Create each repository
gh repo create ksi-compositions --description "KSI Compositions" --public
gh repo create ksi-evaluations --description "KSI Evaluations" --public  
gh repo create ksi-capabilities --description "KSI Capabilities" --public
```

### 2. Set Up Local Repos

```bash
# Create and populate each repository
mkdir -p ksi_repositories/ksi-compositions
cd ksi_repositories/ksi-compositions
git init
# Copy content from var/lib/compositions
cp -r ../../var/lib/compositions/* .
cp ../../temp_repos/ksi-compositions/README.md .
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/ksi-compositions.git
git push -u origin main
cd ../..
```

### 3. Add Submodules

```bash
# Add submodules
git submodule add https://github.com/YOUR_USERNAME/ksi-compositions.git var/lib/compositions
git submodule add https://github.com/YOUR_USERNAME/ksi-evaluations.git var/lib/evaluations
git submodule add https://github.com/YOUR_USERNAME/ksi-capabilities.git var/lib/capabilities
```

## Verification

After setup, verify:

1. **Repositories exist on GitHub**
2. **Submodules are properly configured**
3. **Content is accessible**
4. **Git operations work**

```bash
# Check submodule status
git submodule status

# Check repository info
python -c "
import asyncio
from ksi_common.git_utils import git_manager
async def test():
    info = await git_manager.get_repository_info('compositions')
    print(f'Repository: {info.path}')
    print(f'URL: {info.url}')
    print(f'Branch: {info.branch}')
asyncio.run(test())
"
```

## Success Indicators

✅ **Setup Complete When:**
- Three repositories exist on GitHub
- Submodules are active in main repository
- `python test_git_integration.py` passes all tests
- Components can be saved/forked with git commits
- Submodule sync operations work

## Next Steps

After successful setup:
1. **Test component operations** in KSI
2. **Create new compositions** to verify git commits
3. **Fork existing compositions** to test lineage
4. **Sync submodules** to test federation
5. **Share repositories** with collaborators

## Support

If you encounter issues:
1. Check GitHub CLI authentication
2. Verify repository permissions
3. Check git configuration
4. Review error messages in detail
5. Try manual setup as fallback

The federated architecture is now ready for collaborative development!