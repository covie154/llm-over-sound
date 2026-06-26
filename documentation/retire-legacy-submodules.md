# Retiring Legacy ggwave and quiet Git Submodules

## Background

`ggwave`, `quiet`, and `minimodem` are git submodules (mode 160000 in the index).
There is no `.gitmodules` file — the entries exist only in the git index. The
transport is now minimodem; `ggwave` and `quiet` are no longer needed. `minimodem`
must be kept.

## Why This Is a Manual Step

Git submodule removal is a destructive index operation that rewrites history-adjacent
index state. It must be done consciously by the developer. Claude does not run
destructive git commands without explicit instruction.

## Commands to Run (once)

```sh
git rm ggwave
git rm quiet
git commit -m "chore: remove retired ggwave and quiet submodules"
```

`git rm` on a submodule removes the index entry and the working-tree directory.
The actual upstream repos are not affected. After committing, the directories will
no longer appear in `git status` as untracked submodule entries.

## After Removal

The bare `ggwave` line in `.gitignore` was there to suppress the submodule directory
from appearing as untracked. After `git rm ggwave`, that entry can also be removed,
but it is harmless to leave it.

## minimodem

`minimodem` stays as-is — it is the active transport submodule and must not be removed.
