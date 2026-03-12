#!/bin/bash

echo "🚀 CodeGate Deploy Starting..."

# copy latest code
cp /storage/emulated/0/Download/main.py bot.py

# git add
git add .

# commit
git commit -m "auto deploy $(date)" || echo "No changes"

# detect branch
branch=$(git branch --show-current)

# push
git push origin $branch

echo "✅ Deploy Done"
