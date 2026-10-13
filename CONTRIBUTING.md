# Contributing to DX-OSD

Thank you for your interest in contributing to **DX-OSD (Open-Core DX-Lab)**! This project strictly enforces 100% pure Free and Open Source Software (FOSS) under OSI-approved licenses (AGPL-3.0 and MIT).

---

## 🛠️ Contribution Workflow

To maintain code quality, test coverage, and smooth team collaboration, please adhere to this process:

### 1. Find or Report an Issue
Before writing code:
- Search existing [GitHub Issues](https://github.com/giabuh/dx-osd/issues) to avoid duplicate work.
- If proposing a bug fix or new capability, open an issue detailing the context, reproduction steps, or architecture rationale.

### 2. Branching Model (Git Flow)
Always create a descriptive branch from `main`:
```bash
git checkout -b feat/conversational-memory   # New features or capabilities
git checkout -b fix/webhook-signature        # Bug fixes
git checkout -b docs/update-architecture     # Documentation updates
```

### 3. Development & Testing Discipline (TDD)
- **Zero regressions**: Ensure existing unit and integration tests pass before and after your change.
- **Run tests locally**:
  ```bash
  python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests -v
  ```
- **Never destroy shared state**: Do not run `docker compose down -v` or prune persistent volumes on development stacks.

### 4. Commit Standards
Follow [Conventional Commits](https://www.conventionalcommits.org/):
- Format: `type(scope): brief explanation in imperative mood`
- Examples:
  - `feat(bot): add Chatwoot typing toggle and media attachment dispatching`
  - `fix(chatwoot): default conversation list to all statuses`
  - `docs(roadmap): record conversational AI experience and memory milestone`
- **Stage explicit paths only**: Never use `git add .` or `git add -A`.

### 5. Open a Pull Request (PR)
1. Push your branch to the remote repository.
2. Open a Pull Request against `main`.
3. Provide a clear summary of changes, linked issues, and verification proof (quote actual test command outputs).
4. Request a review from maintainers.

---

## 🎨 Coding & Licensing Standards

1. **Licensing**:
   - `chatwoot/`: Vendored Community Edition under MIT.
   - `crm/`: Frappe CRM under AGPL-3.0.
   - `frappe-custom/mmm_custom/`: Custom app under MIT.
   - All third-party additions must be OSI-approved (no proprietary or closed-source code).
2. **Language**: Code, docstrings, comments, commit messages, and documentation must be written in **English**. User-facing UI labels are in Vietnamese.
3. **Security**: Webhook endpoints must enforce HMAC-SHA256 signature verification and anti-replay timestamps. Ports must bind strictly to `127.0.0.1`.

---

Thank you for helping build an open-core digital transformation platform for Vietnam's SMEs and education centers!
