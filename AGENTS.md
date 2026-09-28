# UI/UX Quality Guidelines for this Project
- Every interactive component MUST support visible focus-visible states.
- Component previews must include state toggles (default, hover, loading, disabled).
- Avoid layout shift (CLS); use explicit min-height/widths on dynamic panels.

# Agent Execution Guidelines (Speed & Focus)
To prevent long-running loops, timeouts, or hanging behavior, follow these constraints on every task:

- **Targeted Scope:** Do not scan, grep, or read directories outside of the immediate feature area unless explicitly requested.
- **Step-by-Step Execution:** For complex tasks, outline a brief 3-step bulleted plan first and wait for confirmation (or proceed step-by-step) rather than executing a massive monolithic block of changes.
- **Minimal Boilerplate:** Do not rewrite or output unmodified template files. Keep code patches concise and localized to what needs to change.