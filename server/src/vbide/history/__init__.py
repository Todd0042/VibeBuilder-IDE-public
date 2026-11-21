"""Change history: every agent edit in /workspace, grouped into change sets, kept for diffs and restores.

store.py     SQLite index + compressed, de-duplicated content blobs; the rolling size cap.
recorder.py  watches the workspace (inotify), snapshots settled files, opens/closes change sets.
diffing.py   unified hunks with a few lines of context (the agy-style review).
routes.py    /api/v1/history.
"""
