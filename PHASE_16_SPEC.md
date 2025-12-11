# Phase 16: Inspector Mode - MINIMAL

Create read-only inspector API:

1. **runtime/inspector.py**: Inspector class with methods:
   - get_task(task_id)
   - get_task_history(task_id)
   - get_task_artifacts(task_id)
   - get_task_events(task_id)
   - get_task_summary(task_id)

2. **engine.py**: Add create_inspector() method

3. **Tests**: 12+ tests covering all inspector methods

Minimal: Read-only queries, no stepping/pausing/mutation.
Files: inspector.py, modify engine.py, test file.
