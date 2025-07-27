#!/usr/bin/env python3
"""
Repository Setup Script for KSI Git Submodule Architecture

This script:
1. Creates the three component repositories
2. Migrates existing var/lib content
3. Initializes git repositories
4. Sets up the submodule structure
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

def run_command(cmd: List[str], cwd: Path = None) -> tuple:
    """Run a command and return (success, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            check=False
        )
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def create_repository_structure():
    """Create the repository directory structure."""
    repo_base = Path("ksi_repositories")
    repo_base.mkdir(exist_ok=True)
    
    repos = {
        "ksi-compositions": {
            "description": "KSI Compositions - Agent profiles, orchestrations, and components",
            "directories": [
                "profiles", "profiles/base", "profiles/agents", "profiles/agents/conversation",
                "profiles/agents/core", "profiles/agents/creative", "profiles/agents/greetings",
                "profiles/agents/specialized", "orchestrations", "orchestrations/patterns",
                "fragments", "fragments/components", "fragments/components/conversation_control",
                "fragments/components/conversation_patterns", "fragments/components/injections",
                "fragments/prompts", "patterns", "schemas"
            ]
        },
        "ksi-evaluations": {
            "description": "KSI Evaluations - Test suites, results, and evaluation frameworks",
            "directories": [
                "test_suites", "results", "judge_bootstrap", "judge_demo_results",
                "judge_schemas", "prompt_iterations", "schemas", "evaluators",
                "iteration_results"
            ]
        },
        "ksi-capabilities": {
            "description": "KSI Capabilities - Capability definitions and permission systems",
            "directories": [
                "schemas", "plugins", "permissions", "permissions/filesystem",
                "permissions/profiles", "permissions/tools"
            ]
        }
    }
    
    for repo_name, config in repos.items():
        repo_path = repo_base / repo_name
        repo_path.mkdir(exist_ok=True)
        
        # Create directory structure
        for dir_name in config["directories"]:
            (repo_path / dir_name).mkdir(parents=True, exist_ok=True)
        
        # Copy existing README if it exists
        readme_src = Path("temp_repos") / repo_name / "README.md"
        readme_dst = repo_path / "README.md"
        if readme_src.exists():
            shutil.copy2(readme_src, readme_dst)
        
        print(f"Created repository structure: {repo_path}")
    
    return repo_base, repos

def migrate_content():
    """Migrate existing var/lib content to new repositories."""
    source_base = Path("var/lib")
    repo_base = Path("ksi_repositories")
    
    if not source_base.exists():
        print("Warning: var/lib directory not found, skipping content migration")
        return
    
    # Migration mappings
    migrations = {
        "compositions": "ksi-compositions",
        "evaluations": "ksi-evaluations",
        "capabilities": "ksi-capabilities"
    }
    
    for source_dir, target_repo in migrations.items():
        source_path = source_base / source_dir
        target_path = repo_base / target_repo
        
        if source_path.exists():
            print(f"Migrating {source_path} -> {target_path}")
            
            # Copy all files and directories
            for item in source_path.rglob("*"):
                if item.is_file():
                    relative_path = item.relative_to(source_path)
                    target_file = target_path / relative_path
                    
                    # Ensure target directory exists
                    target_file.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Copy file
                    shutil.copy2(item, target_file)
                    print(f"  Copied: {relative_path}")
        
        # Handle capability_mappings.yaml special case
        if source_dir == "capabilities":
            mapping_file = source_base / "capability_mappings.yaml"
            if mapping_file.exists():
                target_file = target_path / "capability_mappings.yaml"
                shutil.copy2(mapping_file, target_file)
                print(f"  Copied: capability_mappings.yaml")

def initialize_git_repositories(repo_base: Path, repos: Dict):
    """Initialize git repositories."""
    for repo_name, config in repos.items():
        repo_path = repo_base / repo_name
        
        print(f"Initializing git repository: {repo_path}")
        
        # Initialize git repository
        success, stdout, stderr = run_command(["git", "init"], repo_path)
        if not success:
            print(f"Error initializing git in {repo_path}: {stderr}")
            continue
        
        # Create .gitignore
        gitignore_content = """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Logs
*.log

# Temporary files
*.tmp
*.temp
.cache/
"""
        
        with open(repo_path / ".gitignore", "w") as f:
            f.write(gitignore_content)
        
        # Add all files
        success, stdout, stderr = run_command(["git", "add", "."], repo_path)
        if not success:
            print(f"Error adding files in {repo_path}: {stderr}")
            continue
        
        # Initial commit
        commit_message = f"Initial commit for {repo_name}"
        success, stdout, stderr = run_command(
            ["git", "commit", "-m", commit_message], 
            repo_path
        )
        if not success:
            print(f"Error committing in {repo_path}: {stderr}")
            continue
        
        print(f"  ✓ Initialized git repository with initial commit")

def create_github_commands_script(repo_base: Path, repos: Dict):
    """Create a script with GitHub commands to run."""
    script_content = """#!/bin/bash
# GitHub Repository Creation Script
# Run this script to create the GitHub repositories

echo "Creating GitHub repositories for KSI components..."

# Check if gh CLI is available
if ! command -v gh &> /dev/null; then
    echo "Error: GitHub CLI (gh) is not installed"
    echo "Please install it: https://cli.github.com/"
    exit 1
fi

# Check authentication
if ! gh auth status &> /dev/null; then
    echo "Error: Not authenticated with GitHub"
    echo "Please run: gh auth login"
    exit 1
fi

# Create repositories
"""
    
    for repo_name, config in repos.items():
        script_content += f"""
echo "Creating repository: {repo_name}"
cd ksi_repositories/{repo_name}
gh repo create {repo_name} --description "{config['description']}" --public
git remote add origin https://github.com/$(gh api user --jq .login)/{repo_name}.git
git push -u origin main
cd ../..
"""
    
    script_content += """
echo "All repositories created successfully!"
echo "Next steps:"
echo "1. Update .gitmodules with actual repository URLs"
echo "2. Add submodules to main KSI repository"
echo "3. Test the complete integration"
"""
    
    script_path = Path("create_github_repos.sh")
    with open(script_path, "w") as f:
        f.write(script_content)
    
    # Make executable
    os.chmod(script_path, 0o755)
    
    print(f"Created GitHub setup script: {script_path}")
    return script_path

def create_submodule_setup_script():
    """Create a script to set up submodules."""
    script_content = """#!/bin/bash
# Submodule Setup Script
# Run this script AFTER creating GitHub repositories

echo "Setting up git submodules..."

# Remove existing var/lib if it exists
if [ -d "var/lib" ]; then
    echo "Backing up existing var/lib to var/lib.backup"
    mv var/lib var/lib.backup
fi

# Add submodules (replace USERNAME with actual GitHub username)
USERNAME=$(gh api user --jq .login)

echo "Adding submodules for user: $USERNAME"

git submodule add https://github.com/$USERNAME/ksi-compositions.git var/lib/compositions
git submodule add https://github.com/$USERNAME/ksi-evaluations.git var/lib/evaluations
git submodule add https://github.com/$USERNAME/ksi-capabilities.git var/lib/capabilities

# Initialize and update submodules
git submodule update --init --recursive

# Update .gitmodules with correct URLs
sed -i '' "s/ksi-project/$USERNAME/g" .gitmodules

echo "Submodules set up successfully!"
echo "Testing git submodule integration..."
python test_git_integration.py
"""
    
    script_path = Path("setup_submodules.sh")
    with open(script_path, "w") as f:
        f.write(script_content)
    
    # Make executable
    os.chmod(script_path, 0o755)
    
    print(f"Created submodule setup script: {script_path}")
    return script_path

def main():
    """Main setup function."""
    print("🚀 Setting up KSI Git Submodule Architecture")
    print("=" * 50)
    
    # Step 1: Create repository structure
    print("\n1. Creating repository structure...")
    repo_base, repos = create_repository_structure()
    
    # Step 2: Migrate content
    print("\n2. Migrating existing content...")
    migrate_content()
    
    # Step 3: Initialize git repositories
    print("\n3. Initializing git repositories...")
    initialize_git_repositories(repo_base, repos)
    
    # Step 4: Create GitHub setup script
    print("\n4. Creating GitHub setup script...")
    github_script = create_github_commands_script(repo_base, repos)
    
    # Step 5: Create submodule setup script
    print("\n5. Creating submodule setup script...")
    submodule_script = create_submodule_setup_script()
    
    print("\n" + "=" * 50)
    print("✅ Repository setup complete!")
    print("\nNext steps:")
    print("1. Run the GitHub setup script:")
    print(f"   ./{github_script.name}")
    print("2. Run the submodule setup script:")
    print(f"   ./{submodule_script.name}")
    print("3. Test the integration:")
    print("   python test_git_integration.py")
    print("\nRepository structure created in: ksi_repositories/")
    
    # List created repositories
    print("\nCreated repositories:")
    for repo_name in repos.keys():
        repo_path = repo_base / repo_name
        print(f"  📁 {repo_path}")

if __name__ == "__main__":
    main()