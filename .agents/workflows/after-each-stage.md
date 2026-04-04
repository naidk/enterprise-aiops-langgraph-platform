---
description: Run after each development stage - validate, fix errors, and commit
---

# After-Each-Stage Workflow

This workflow must be followed after every development prompt/stage.

## Step 1: Run the Code ✅

### Check imports
```
python -c "import app"
```

### Or run the main file
```
python app/main.py
```

### If FastAPI app exists
```
uvicorn app.main:app --reload
```
(Run briefly to confirm it starts, then Ctrl+C)

### If tests exist
```
pytest
```

## Step 2: Fix Errors ❌

If any of the above fail, immediately fix:
- Import errors
- Missing packages (add to requirements.txt and install)
- Wrong file paths or module references
- Syntax/runtime errors

Do NOT move to the next stage until all errors are resolved.

## Step 3: Git Commit ✅

```
git add .
git commit -m "Stage X: <short description of what was implemented>"
```

Replace `X` with the stage number and write a meaningful commit message.
