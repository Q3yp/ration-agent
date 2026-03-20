# Project Rules

## Agent Rule: Use `repcon` During Development

- At the start of a task, orient first:
  - Run `repcon overview`.
  - If the task touches an existing feature flow, run `repcon path list "<path>"`.
  - Use `repcon search <term>` to find relevant files, functions, and feature paths.
  - Use `repcon file <path>` and `repcon query <fn>` to locate entry points/callers/callees before making changes.
- Do not run `repcon update` by default at the start of a task on an already-initialized project.
  - Exception: if you suspect the context DB is stale, run `repcon update --no-refresh` as a read-only drift check.
- After you finish code changes (end of task), run `repcon update` to close the loop:
  - It refreshes the context DB, then reports only what your changes affected (changed files needing descriptions, affected feature paths).
  - Follow the "Suggested Commands" it prints (typically `repcon describe ...` and/or `repcon path list "<path>"`).
- Use `repcon update --all` only when you intentionally want the full backlog; use `repcon update --include-skipped` only when working in areas excluded by discovery rules.
