# Agent rules for this project

These rules apply to every AI coding agent working here (Claude Code reads them through CLAUDE.md, agy
reads this file directly). They are a starting point added by VibeBuilder IDE: edit them to fit the
project, or delete this file if you don't want them.

## 1. Security comes first
- Treat every input (forms, URLs, files, API responses, environment) as untrusted: validate it, and
  escape or parameterize it before it reaches HTML, SQL, a shell command or a file path.
- Never put secrets (API keys, passwords, tokens, private keys) in code, commits, logs or error
  messages. Read them from environment variables or a `.env` file, make sure `.env` is in
  `.gitignore`, and keep a `.env.example` with placeholder values next to it.
- Every endpoint or page that reads or changes private data must check who is asking.
- Never weaken a security setting (CORS `*`, disabled TLS checks, `--no-verify`, `chmod 777`,
  turning off auth "for now") to make an error go away. Fix the cause, or ask.
- Add dependencies only when needed, from the official registry, with exact versions in the lock file.

## 2. Keep the code organized
- No file over 500 lines. When a file is getting close, split it by responsibility before adding more.
- One clear job per file, module or function. Put new code where code of that kind already lives.
- Reuse what exists before writing something new: search the project for an existing helper first.
- Name things for what they do. No dead code, commented-out blocks or placeholder stubs left behind.
- If a change only fits by bolting it on, stop and propose the refactor that makes it fit cleanly.

## 3. Commit often, push at milestones
- Commit at the end of every task or session, with a message that says what changed and why.
- Commit before any large or risky change, so it can be undone.
- Push when a feature works end to end (a milestone), not with broken code.
- Never commit secrets, build output or dependency folders (`node_modules`, `.venv`, `dist`...):
  keep `.gitignore` up to date.
- Never force-push, rewrite history or delete branches unless asked to.

## 4. No silent errors
- Every error must be visible, with full details, to whoever runs the software: in the terminal,
  the log, the app's own window or the browser console. Say what failed, where (file, function,
  request or input) and why (the underlying error and its stack trace), and what to do about it.
- Never swallow an error: no empty `catch`/`except`, no `catch` that only logs at a level nobody
  sees, no `|| true`, no default value or `?.` that hides a failure, no unhandled promise rejection,
  no ignored return code. Catch an error only to add context and re-raise it, to recover on purpose
  (and report that you did), or to show it.
- Never silently fall back to fake, default or cached data. If a fallback is used, say so.
- The program must not appear to work when it doesn't: no blank screen, endless spinner, or
  "Something went wrong" with nothing behind it.
- Secrets never appear in any error, log or message: mask passwords, API keys, tokens, cookies,
  connection strings and private keys (e.g. `sk-…a1b2`) before printing anything that might hold them.
- If the software serves visitors (a public website or API), those visitors get a plain message and
  a reference ID, never stack traces, file paths, SQL, server versions or config. The full details,
  under that same ID, go to the logs for whoever runs it.

## 5. Prove it works
- Run the app and verify changes work end to end after every feature or bugfix. Never say something
  works without having tested it.
- Prefer realistic end-to-end (E2E) verification for complex features and before major releases. Do
  not waste time writing shallow, post-hoc unit tests for trivial code.
- When something fails, find the root cause. Don't skip or loosen tests to make them pass.

## 6. Don't guess, don't wreck
- Check the real documentation and the installed versions before using a library or API; don't
  invent functions or options.
- When the request is unclear or a decision is the owner's to make, ask a short question first.
- Never delete or overwrite files, data or databases you didn't create without asking. Back up
  before migrations.
- Make small, focused changes. Don't rewrite working code that wasn't part of the task.
- Keep the README current: what the project is, how to install, run and test it.
