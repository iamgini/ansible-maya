# Copyright 2026 Ansible Maya Contributors
# Licensed under the Apache License, Version 2.0

"""Execution specification generator - two-phase playbook generation."""

from typing import Optional
from uuid import uuid4

from ansible_maya.handlers.orchestrator import AIOpsEvent


class ExecutionSpec:
    """Execution specification for playbook generation."""

    def __init__(
        self,
        spec_id: str,
        event: AIOpsEvent,
        steps: str,
        model: str,
        requires_approval: bool = True,
    ):
        self.spec_id = spec_id
        self.event = event
        self.steps = steps
        self.model = model
        self.requires_approval = requires_approval


class SpecGenerator:
    """Generate execution specifications from events."""

    def __init__(self, llm_provider):
        self.llm_provider = llm_provider

    async def generate_spec(self, event: AIOpsEvent) -> ExecutionSpec:
        """Generate execution plan from event.

        Args:
            event: Infrastructure event to remediate

        Returns:
            ExecutionSpec with numbered steps in plain English
        """
        spec_prompt = self._build_spec_prompt(event)

        # Use cheaper/faster model for spec
        spec_text = await self.llm_provider.generate(spec_prompt, model="haiku", max_tokens=1000)

        spec_id = str(uuid4())

        return ExecutionSpec(
            spec_id=spec_id,
            event=event,
            steps=spec_text,
            model="haiku",
            requires_approval=True,
        )

    def _build_spec_prompt(self, event: AIOpsEvent) -> str:
        """Build prompt for spec generation."""
        return f"""Given this infrastructure event, describe the remediation steps in plain English.

Event Type: {event.event_type}
Description: {event.description}
Host: {event.host}
Severity: {event.severity}

Return ONLY a numbered list of remediation actions. Be specific but concise.
Focus on WHAT to do, not HOW (no Ansible syntax).

Example format:
1. Check current disk usage on /var partition
2. Identify log files older than 30 days
3. Archive old logs to /backup directory
4. Delete archived logs from /var/log
5. Verify disk space recovered

Now generate steps for the event above:"""
