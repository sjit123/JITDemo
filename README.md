# JIT Access Demo

## 1. 30-Second Pitch

Standing access means long-lived credentials are always available, even when no one is actively working, and that convenience is why it became the default pattern across many teams and systems. The risk is that once one of those credentials leaks, the attacker gets durable access for as long as that secret remains valid, which can be weeks, months, or longer. Just-in-Time access flips that model by issuing short-lived, scoped credentials only at the moment of need and revoking them as soon as work is done. This demo shows that same primitive across humans, apps, and agents so the lesson is not role-specific. If a token leaks under JIT, the blast radius is bounded by lease time and policy scope, and every action is auditable.

## 2. Run Instructions

```bash
git clone <your-repo-url>
cd jit-access-demo
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Note: everything runs in-memory. Restart = fresh state. That's intentional.

## 3. 5-Minute Demo Script

### Step 1 (60s) - The Problem

Open the Standing Access page. Show the hardcoded credential. Move slider to 365. Say: "A credential that leaked today is still valid next year."

### Step 2 (90s) - Human JIT

Select alice@corp. Run Human scenario on JIT Flow page. Point at the TTL countdown. Say: "Same leak here buys an attacker 60 seconds, not a year."

### Step 3 (90s) - Agent JIT + Denial

Switch to research-agent. Run Agent denial path. Let the reasoning trace stream. Point at the access_denied event. Say: "The agent reasoned its way to the wrong policy. The vault stopped it. The audit log recorded it."

### Step 4 (60s) - Admin View

Open Vault Admin. Run a Human scenario with a long TTL. Show the live lease. Hit Revoke. Switch to Audit Log. Show the revoked event appear. Say: "Full revocation in one click. Audit trail is automatic."

### Step 5 (20s) - Close

"Same primitive, three personas, zero standing credentials."

## 4. MiniVault -> HashiCorp Vault Mapping

| MiniVault | HashiCorp Vault equivalent |
|---|---|
| MiniVault class | hvac.Client |
| Policy model | Vault policy HCL + database roles |
| secrets_engine.issue() | vault read database/creds/<role> |
| JWT with exp claim | Vault lease with lease_duration |
| LeaseManager.revoke() | vault lease revoke <lease_id> |
| Signer (HS256) | Vault's internal token store |
| AuditLog | Vault audit device (file/syslog) |
| DBProxy scope check | Database secrets engine + Vault Agent |

The contract your application code sees - request, use, release - is identical. Swap the import, point at a real Vault address, done.

## 5. Architecture Diagram

```
                    ┌─────────────────────────────────────┐
                    │          Streamlit UI               │
                    │  (Standing | JIT | Admin | Audit)   │
                    └──────────────┬──────────────────────┘
                                   │
        ┌──────────────────────────┼──────────────────────────┐
        ▼                          ▼                          ▼
   ┌─────────┐              ┌────────────┐             ┌────────────┐
   │ Persona │              │ MiniVault  │             │  DBProxy   │
   │ runners │──request─────▶│            │             │            │
   │         │◀──token──────│  policies  │             │ verify tok │
   │ human   │              │  leases    │◀───validate─│ check scope│
   │  app    │──token+op────▶│  signer    │             │ run query  │
   │ agent   │              │  audit     │             │            │
   └─────────┘              └─────┬──────┘             └─────┬──────┘
                                  │                          │
                                  ▼                          ▼
                            ┌──────────┐              ┌─────────────┐
                            │ Sweeper  │              │  SQLite :   │
                            │ (thread) │              │  memory:    │
                            │ revokes  │              │  customers  │
                            │ expired  │              └─────────────┘
                            └──────────┘
```

## 6. What's Intentionally Missing

- No approval workflow (model is plumbed, UI not wired)
- No persistence (restart resets everything)
- No real LLM in the agent persona
- KV secrets engine not implemented
