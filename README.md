# ShadowFix AI

ShadowFix is a multi-agent QA and repair desk. It reproduces a registered application crash, searches that tenant's AST index for the culprit, drafts a patch, scores it, and stops. An admin approval is the only action that mints a 15-minute AWS session.

The included target is Shopkart, a small store whose `SHADOW` coupon divides by zero.

## Agents

| Agent | Job |
| --- | --- |
| Breaker | Reproduces the Shopkart checkout crash and records the traceback. Playwright, Toxiproxy, and Locust stay opt-in and capped. |
| SRE | Reads the demo workflow and reports that this failure is application code. It does not call STS. |
| Detective | Searches Qdrant with a required `tenant_id` filter. |
| Coder | Repairs `demo-shopkart/api/checkout.py`. Uses Gemini 2.5 Pro when `GEMINI_API_KEY` is set, otherwise a deterministic repair. |
| Reviewer | Secret-scans the diff, scores it (threshold 85), and prepares a pull request. Untrusted code runs only in E2B. |

LangGraph runs that sequence. `backend/temporal_worker.py` is the durable version: the workflow waits on an approve signal before the deploy activity.

## Security invariants

- Qdrant upsert and search both require `tenant_id`. There is no unscoped search method.
- Ansible tasks cannot use `ansible.builtin.shell`, `ansible.builtin.command`, or `rm -rf`.
- Public callers cannot point the breaker at an arbitrary host. The demo target is `shopkart://local`.
- AWS writes do not use long-lived keys. `assume_role` is called with `DurationSeconds=900` only after a one-time approval token. `AKIA` keys are rejected. The API response never includes the secret or session token.
- Missing `E2B_API_KEY` skips execution. It does not start a local container.

## Run the demo

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
pip install -r backend\requirements-cloud.txt   # optional: Gemini, Temporal, E2B
uvicorn main:app --app-dir backend --port 8000
```

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open http://127.0.0.1:5183 , reproduce the crash, then open Admin. The local admin key is `change-me` until you set `ADMIN_API_KEY`. Approve reports a dry run unless `SHADOWFIX_DEPLOY_ROLE_ARN` is set.

Shopkart itself:

```powershell
uvicorn main:app --app-dir demo-shopkart/api --port 8010
cd demo-shopkart/web
npm install
npm run dev
```

The storefront is http://127.0.0.1:5184 . Coupon `SHADOW` returns the division error from the API.

## Tests

```powershell
pytest
```

## Configuration

Copy `.env.example` to `.env`. Empty keys are safe: the demo pipeline, the score, and the dry-run approval all run without cloud accounts.

Pull requests are published only when `GITHUB_TOKEN`, `GITHUB_REPOSITORY`, and `SHADOWFIX_OPEN_PR=true` are all set. The token is read from the environment, not from a GitHub CLI login on the machine.
