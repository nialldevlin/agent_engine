# Git Commands Guide: Basic Operations

## Introduction
Git is a powerful version control system that helps developers manage and track changes in their code. This guide covers the most commonly used Git commands.

## Basic Git Workflow Commands

### 1. git init
Initialize a new Git repository
```bash
git init
```
- Creates a new local repository in the current directory
- Sets up necessary Git tracking files

### 2. git add
Stage changes for commit
```bash
# Stage a specific file
git add filename.txt

# Stage all modified files
git add .

# Stage multiple specific files
git add file1.txt file2.txt
```
- Prepares files to be included in the next commit
- Tracks new or modified files

### 3. git commit
Record changes to the repository
```bash
# Commit with a message
git commit -m "Descriptive commit message"

# Stage and commit all modified files
git commit -am "Commit message"
```
- Creates a snapshot of your current project state
- Always include a clear, descriptive message

### 4. git push
Upload local repository content to remote repository
```bash
# Push to current branch
git push

# Push to a specific branch
git push origin branch_name

# First time pushing a new branch
git push -u origin branch_name
```
- Shares your commits with remote repository
- `-u` sets up tracking for future pushes

### 5. git status
Check repository status
```bash
git status
```
- Shows which files are staged, unstaged, or untracked
- Helps understand current state of your repository

### 6. git log
View commit history
```bash
# Basic log
git log

# Compact log with one line per commit
git log --oneline
```
- Displays commit details
- Helps track project changes

## Best Practices
- Commit frequently
- Write clear, descriptive commit messages
- Use branches for new features or experiments
- Pull before you push to avoid conflicts

## Conclusion
Mastering these basic Git commands will significantly improve your version control workflow and collaboration skills.