# Approval Workflows for Ansible Maya

This document explains different approval mechanisms for playbook generation and their compatibility with various execution environments.

## Overview of Approval Methods

| Method | Storage | AAP/EDA Compatible | Use Case |
|--------|---------|-------------------|----------|
| **Spec-Kit (Current)** | In-memory | ❌ No | Local CLI, interactive testing |
| **Multi-Agent Review** | None (inline) | ✅ Yes | Automated quality enhancement |
| **External Approval Service** | Redis/PostgreSQL | ✅ Yes | Enterprise workflows with ticketing |
| **Git-based Approval** | Git repository | ✅ Yes | GitOps-style approval via PR |
| **Slack/Teams Approval** | External service | ✅ Yes | Chat-based approval workflows |

---

## 1. Spec-Kit (Current Implementation)

**File:** `ansible_maya/api/routes/specs.py`

### How it works
```bash
# Phase 1: Generate spec
POST /api/v1/specs/plan
→ Returns spec_id (stored in-memory)

# Human reviews spec...

# Phase 2: Approve & generate
POST /api/v1/specs/{spec_id}/generate
→ Generates playbook from approved spec
```

### Limitations
- ❌ **In-memory storage** - lost on API restart
- ❌ **No AAP/EDA support** - jobs can't pause mid-execution
- ❌ **No persistence** - Phase 1 and Phase 2 must be in same API session

### Use Cases
- ✅ Local CLI workflows
- ✅ Interactive API testing
- ✅ Manual approval in scripts with `pause`

### Example (Local Playbook)
```yaml
- name: Generate with approval (local only)
  hosts: localhost
  tasks:
    - name: Get execution plan
      ansible.builtin.uri:
        url: http://localhost:8000/api/v1/specs/plan
        method: POST
        body: {...}
      register: spec

    - name: Display plan for review
      ansible.builtin.debug:
        msg: "{{ spec.json.steps }}"

    - name: Wait for approval
      ansible.builtin.pause:
        prompt: "Press Enter to approve, Ctrl+C to cancel"

    - name: Generate from approved spec
      ansible.builtin.uri:
        url: "http://localhost:8000/api/v1/specs/{{ spec.json.spec_id }}/generate"
        method: POST
        body: {"approved": true}
      register: playbook
```

**This will NOT work in AAP** because `pause` requires interactive terminal.

---

## 2. Multi-Agent Review (Recommended for AAP/EDA)

**File:** `ansible_maya/api/routes/events.py` (query parameter)

### How it works
```bash
# Single API call with automated review
POST /api/v1/events/generate?multi_agent_review=true
→ Generates playbook with security + best practices review
→ Returns enhanced playbook with higher confidence score
```

### Advantages
- ✅ **AAP/EDA compatible** - single synchronous call
- ✅ **No storage needed** - fully stateless
- ✅ **Automated quality** - no human intervention needed
- ✅ **5-15% confidence boost** - adversarial review improves quality

### Use Cases
- ✅ Automated AIOps workflows
- ✅ EDA rulebook actions
- ✅ AAP job templates
- ✅ High-stakes production events

### Example (AAP/EDA Compatible)
```yaml
- name: Generate with multi-agent review
  ansible.builtin.uri:
    url: "{{ maya_api_url }}?multi_agent_review=true"
    method: POST
    body_format: json
    body:
      event_type: "{{ event_type }}"
      description: "{{ event_description }}"
      host: "{{ event_host }}"
      severity: "{{ event_severity }}"
    timeout: 180  # Multi-agent takes longer
  register: playbook
```

**This works everywhere** - no state, no pause, just enhanced generation.

---

## 3. External Approval Service (Future Implementation)

### Architecture
```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│ Maya API    │────▶│ Redis/PG     │────▶│ Approval UI │
│             │     │ (persistent) │     │ (Web/Slack) │
└─────────────┘     └──────────────┘     └─────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │ AAP Workflow │
                    │ (polls)      │
                    └──────────────┘
```

### How it would work
```bash
# Phase 1: Generate spec (saves to Redis with TTL)
POST /api/v1/specs/plan
→ Returns approval_url and spec_id

# Human approves via web UI or Slack
# Approval stored in Redis: spec:{spec_id}:status = "approved"

# AAP workflow polls for approval
GET /api/v1/specs/{spec_id}/status
→ Returns {"status": "approved"} or {"status": "pending"}

# Phase 2: Generate (if approved)
POST /api/v1/specs/{spec_id}/generate
→ Generates playbook
```

### Implementation Requirements
- Redis or PostgreSQL for persistent storage
- Approval UI (web dashboard or chat integration)
- Polling mechanism in AAP playbook
- TTL/expiration for abandoned approvals

### Example AAP Workflow
```yaml
- name: Request approval
  ansible.builtin.uri:
    url: "{{ maya_api_url }}/specs/plan"
    method: POST
    body: {...}
  register: approval_request

- name: Send approval link to Slack
  slack:
    msg: "Approve: {{ approval_request.json.approval_url }}"

- name: Poll for approval (max 30 min)
  ansible.builtin.uri:
    url: "{{ maya_api_url }}/specs/{{ spec_id }}/status"
  register: approval_status
  until: approval_status.json.status == "approved"
  retries: 60
  delay: 30  # Check every 30 seconds

- name: Generate playbook
  ansible.builtin.uri:
    url: "{{ maya_api_url }}/specs/{{ spec_id }}/generate"
    method: POST
    body: {"approved": true}
```

**Status:** Not implemented. Requires Redis/PostgreSQL backend.

---

## 4. Git-based Approval (GitOps Pattern)

### How it works
1. Maya generates playbook → commits to `pending/` branch
2. Creates GitHub/GitLab PR automatically
3. Human reviews PR → approves or requests changes
4. On merge → AAP pulls from `main` branch → executes playbook

### Advantages
- ✅ Full audit trail in Git
- ✅ Standard review process (PR comments, approvals)
- ✅ Persistent storage (Git history)
- ✅ Works with existing GitOps workflows

### Example Workflow
```yaml
- name: Generate playbook with Maya
  ansible.builtin.uri:
    url: "{{ maya_api_url }}/events/generate"
    method: POST
    body: {...}
  register: maya_playbook

- name: Create feature branch
  ansible.builtin.command:
    cmd: git checkout -b "maya-{{ event_type }}-{{ ansible_date_time.epoch }}"

- name: Save playbook to git
  ansible.builtin.copy:
    content: "{{ maya_playbook.json.playbook }}"
    dest: "playbooks/generated/{{ event_type }}.yml"

- name: Commit and push
  ansible.builtin.command:
    cmd: |
      git add playbooks/generated/{{ event_type }}.yml
      git commit -m "AI-generated playbook for {{ event_type }}"
      git push origin maya-{{ event_type }}-{{ ansible_date_time.epoch }}

- name: Create pull request
  ansible.builtin.uri:
    url: "https://api.github.com/repos/{{ repo }}/pulls"
    method: POST
    headers:
      Authorization: "token {{ github_token }}"
    body:
      title: "AI-generated playbook: {{ event_type }}"
      head: "maya-{{ event_type }}-{{ ansible_date_time.epoch }}"
      base: "main"
      body: |
        **Event:** {{ event_type }}
        **Confidence:** {{ maya_playbook.json.confidence_score }}
        **Model:** {{ maya_playbook.json.generation_metadata.model }}
        
        Please review and merge to deploy.
```

**Status:** Conceptual. Requires integration with Git provider APIs.

---

## 5. Slack/Teams Approval (ChatOps Pattern)

### How it works
1. Maya generates spec → sends to Slack/Teams with buttons
2. User clicks "Approve" or "Reject" → callback to Maya API
3. Maya generates playbook if approved
4. Returns playbook to AAP workflow

### Advantages
- ✅ Familiar approval interface (chat)
- ✅ Mobile-friendly (approve from phone)
- ✅ Persistent storage in chat history
- ✅ Notifications included

### Example with Slack
```yaml
- name: Generate spec
  ansible.builtin.uri:
    url: "{{ maya_api_url }}/specs/plan"
    method: POST
    body: {...}
  register: spec

- name: Send to Slack for approval
  slack:
    token: "{{ slack_token }}"
    msg: |
      **Execution Plan:** {{ spec.json.steps }}
      **Event:** {{ event_type }}
    attachments:
      - actions:
          - type: button
            text: "✅ Approve"
            url: "{{ maya_api_url }}/specs/{{ spec.json.spec_id }}/approve"
          - type: button
            text: "❌ Reject"
            url: "{{ maya_api_url }}/specs/{{ spec.json.spec_id }}/reject"
  register: slack_msg

- name: Poll for approval response
  ansible.builtin.uri:
    url: "{{ maya_api_url }}/specs/{{ spec.json.spec_id }}/status"
  register: approval_status
  until: approval_status.json.status != "pending"
  retries: 120
  delay: 30  # Poll every 30 seconds for up to 1 hour
```

**Status:** Conceptual. Requires Slack/Teams webhook integration.

---

## Comparison Matrix

| Feature | Spec-Kit | Multi-Agent | External Service | Git-based | Chat-based |
|---------|----------|-------------|------------------|-----------|------------|
| **Storage** | In-memory | None | Redis/DB | Git | External API |
| **AAP Compatible** | ❌ | ✅ | ✅ | ✅ | ✅ |
| **Human Approval** | ✅ | ❌ | ✅ | ✅ | ✅ |
| **Audit Trail** | ❌ | Logs only | Database | Git history | Chat history |
| **Implementation** | ✅ Done | ✅ Done | ❌ Future | ❌ Future | ❌ Future |
| **Mobile Friendly** | ❌ | N/A | Depends | Via Git UI | ✅ |
| **Async Support** | ❌ | N/A | ✅ | ✅ | ✅ |
| **Setup Complexity** | Low | Low | Medium | Medium | High |

---

## Recommendations by Use Case

### For AAP/EDA Automated Workflows
**Use:** Multi-Agent Review (`?multi_agent_review=true`)
- No approval needed, just enhanced quality
- Single synchronous API call
- Works everywhere

### For Interactive CLI/Testing
**Use:** Current Spec-Kit (`/specs/plan` → `/specs/{id}/generate`)
- Simple two-phase flow
- Manual review before generation
- No infrastructure needed

### For Enterprise Production (Future)
**Implement:** External Approval Service with Redis/PostgreSQL
- Async approval workflows
- Web UI for approvals
- Persistent audit trail
- AAP polling support

### For GitOps Teams (Future)
**Implement:** Git-based Approval
- PR-based review process
- Familiar Git workflow
- Full version control

### For ChatOps Teams (Future)
**Implement:** Slack/Teams Approval
- Mobile-friendly approvals
- Chat-native experience
- Quick responses

---

## Migration Path

1. **Today:** Use multi-agent review for AAP/EDA
2. **Short-term:** Implement Redis backend for Spec-Kit
3. **Medium-term:** Add approval UI (web dashboard)
4. **Long-term:** Integrate with Git providers and chat platforms

---

## Configuration Examples

### Enable Multi-Agent Review by Default
```bash
# .env
MAYA_DEFAULT_MULTI_AGENT_REVIEW=true
```

### Configure Redis for Spec Storage (Future)
```bash
# .env
MAYA_SPEC_STORAGE=redis
MAYA_REDIS_URL=redis://localhost:6379/0
MAYA_SPEC_TTL=1800  # 30 minutes
```

### Configure Approval Timeout (Future)
```bash
# .env
MAYA_APPROVAL_TIMEOUT=3600  # 1 hour
MAYA_APPROVAL_NOTIFICATION=slack  # or teams, email
```

---

## Questions?

- **Current limitation:** Spec-Kit is in-memory only
- **Recommended for AAP/EDA:** Use `multi_agent_review=true`
- **Future:** Persistent storage for async approval workflows

See `QUICKSTART.md` for usage examples and `CLAUDE.md` for development guidance.
