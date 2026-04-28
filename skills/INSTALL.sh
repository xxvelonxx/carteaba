#!/bin/bash

echo "🚀 Installing Velon's skills to /mnt/skills/user/"

# Check if running in correct environment
if [ ! -d "/mnt/skills/user" ]; then
    echo "❌ ERROR: /mnt/skills/user directory not found"
    echo "This script must run in Claude's container environment"
    exit 1
fi

# Backup existing if any
if [ "$(ls -A /mnt/skills/user 2>/dev/null)" ]; then
    BACKUP="/home/claude/skills-backup-$(date +%Y%m%d-%H%M%S)"
    echo "📦 Backing up existing skills to $BACKUP"
    mkdir -p $BACKUP
    cp -r /mnt/skills/user/* $BACKUP/
fi

# Copy all skills
echo "📂 Installing skills..."
for skill_dir in */; do
    if [ "$skill_dir" != "INSTALL.sh" ]; then
        skill_name="${skill_dir%/}"
        echo "  ✓ $skill_name"
        cp -r "$skill_name" /mnt/skills/user/
    fi
done

echo ""
echo "✅ Installation complete!"
echo ""
echo "📋 Installed skills:"
ls -1 /mnt/skills/user/

echo ""
echo "🎯 To verify, in new chat say: 'sigamos cazando'"
