# Vercel Skills CLI — optional, project-local discovery backend

The advisor NEVER automatically installs this CLI and NEVER runs `skills add`.

To enable live `skills find` searches, the user must separately review and approve installing the official `skills` npm package at a pinned version. Use a supported Node.js version (the current upstream README specifies Node >=22.20).

From the AgentFlow project root, after reviewing the upstream package and approving network access:

```bash
npm install --prefix .agentflow/tools/skills-cli --save-exact --ignore-scripts skills@<approved-exact-version>
```

Replace `<approved-exact-version>` with an explicitly reviewed version. Never run an unpinned installation in an automated task.

The backend only detects `.agentflow/tools/skills-cli/node_modules/.bin/skills` (or `.agentflow/tools/node_modules/.bin/skills`) and executes **find** with bounded generic search terms. It never selects a global executable from PATH, executes `npx`, or installs any skill.

Network-disabled behavior: the GitHub fallback will also fail; the native-host local suggestions remain available. Source discovery does NOT mean Git provenance or security approval. Review the repository, pinned commit, `SKILL.md`, dependencies, and explicit installation approval through the existing console flow.
