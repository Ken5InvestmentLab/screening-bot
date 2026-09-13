# TV-Free research skills

Reusable Agent Skills for the TV-Free JPX scoring-bot research.

## Skills

- `tvfree-research-supervisor` — coordinates parallel lanes and prevents duplicate/contradictory work.
- `tvfree-experiment-freeze` — preregisters a new experiment before outcomes are opened.
- `tvfree-result-auditor` — audits completed results against the frozen contract.
- `tvfree-handoff-recorder` — writes durable GitHub handoffs for seamless continuation.

These skills intentionally do **not** encode a specific predictive model. The research mechanism must remain free to evolve; the repeatable governance/evaluation workflow is what is standardized.

The user's explicit instructions always take precedence over these skills.
