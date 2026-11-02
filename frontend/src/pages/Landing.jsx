import { useState } from "react";
import { Link } from "react-router-dom";
import LiveDemo from "../components/LiveDemo";

const STACK = [
  "LangGraph",
  "Qdrant",
  "Temporal",
  "Gemini 2.5 Pro",
  "E2B Sandbox",
  "AWS STS",
  "Playwright",
  "Toxiproxy",
  "Locust",
  "Mem0",
  "FastAPI",
  "React Flow",
];

const PILLARS = [
  {
    title: "Reproduce before you guess.",
    body: "The Breaker replays the Shopkart checkout and records the real traceback, so every fix starts from a crash that actually happened.",
    icon: "M4 17l6-6-6-6M12 19h8",
  },
  {
    title: "Search only your own code.",
    body: "Every Qdrant search and upsert needs a tenant_id. There is no unscoped search method to call by mistake.",
    icon: "M11 4a7 7 0 105.2 11.7L21 20.5M11 8v6M8 11h6",
  },
  {
    title: "Score the patch, then stop.",
    body: "The Reviewer secret-scans the diff and scores it against a threshold of 85 before anything reaches a pull request.",
    icon: "M5 13l4 4L19 7",
  },
  {
    title: "Humans hold the keys.",
    body: "No long-lived AWS keys. An admin approval mints a 15-minute session once, and the API never returns the secret.",
    icon: "M12 3l8 3v6c0 4.5-3.2 7.8-8 9-4.8-1.2-8-4.5-8-9V6l8-3z",
  },
];

const AGENTS = [
  {
    n: "01",
    name: "Breaker",
    body: "Reproduces the Shopkart checkout crash and records the traceback. Playwright, Toxiproxy and Locust stay opt-in and capped.",
  },
  {
    n: "02",
    name: "SRE",
    body: "Reads the demo workflow and reports whether the failure is application code or infrastructure. It never calls STS.",
  },
  {
    n: "03",
    name: "Detective",
    body: "Searches the tenant's AST index in Qdrant and ranks the functions most likely to hold the bug.",
  },
  {
    n: "04",
    name: "Coder",
    body: "Repairs the culprit file. Uses Gemini 2.5 Pro when a key is set, and a deterministic repair when it is not.",
  },
  {
    n: "05",
    name: "Reviewer",
    body: "Secret-scans the diff, scores it, prepares the pull request, and runs untrusted code only inside E2B.",
  },
];

const RUN_STEPS = [
  {
    tab: "Crash",
    title: "Replay the failing request",
    body: "The Breaker sends the SHADOW coupon through checkout and keeps the traceback as evidence for every later step.",
    code: [
      ["$", "POST /api/checkout  coupon=SHADOW"],
      ["!", "ZeroDivisionError: float division by zero"],
      ["·", "at compute_total  demo-shopkart/api/checkout.py"],
    ],
  },
  {
    tab: "Culprit",
    title: "Name the file and the function",
    body: "The Detective searches the tenant-filtered AST index and returns ranked symbols with a score for each.",
    code: [
      ["$", "qdrant.search(tenant_id='shopkart', query=traceback)"],
      ["1", "compute_total   checkout.py   0.91"],
      ["2", "apply_coupon    checkout.py   0.64"],
    ],
  },
  {
    title: "Draft the patch and score it",
    tab: "Patch",
    body: "The Coder rewrites the divisor as a multiplier. The Reviewer scans for secrets and scores the diff against the threshold.",
    code: [
      ["-", "return round(subtotal / (1 - discount), 2)"],
      ["+", "return round(subtotal * (1 - discount), 2)"],
      ["✓", "secret scan clean · eval 92 / 85"],
    ],
  },
  {
    tab: "Approval",
    title: "Wait for an admin",
    body: "The workflow pauses on an approve signal. Approval mints one 15-minute AWS session. Without a deploy role it reports a dry run.",
    code: [
      ["$", "POST /api/admin/approve/<incident>"],
      ["·", "assume_role DurationSeconds=900"],
      ["✓", "dry run · expires in 900s"],
    ],
  },
];

const RULES = [
  ["Tenant-scoped search", "Qdrant upsert and search both require a tenant_id. No unscoped method exists."],
  ["Ansible allow-list", "Tasks cannot use ansible.builtin.shell, ansible.builtin.command, or rm -rf."],
  ["Fixed demo target", "Public callers cannot point the Breaker at a host. The target is shopkart://local."],
  ["No long-lived keys", "AKIA keys are rejected. Sessions last 900 seconds and follow a one-time approval token."],
  ["Safe sandbox default", "A missing E2B_API_KEY skips execution. It never starts a local container."],
  ["Kill switch and quotas", "Admins can stop new runs at once, and each tenant has a daily run cap."],
];

const FAQ = [
  [
    "What does ShadowFix actually do?",
    "It reproduces a registered application crash, finds the culprit in that tenant's AST index, drafts a patch, scores it, and stops. A person decides whether anything ships.",
  ],
  [
    "Does it deploy by itself?",
    "No. An admin approval is the only action that mints a 15-minute AWS session. Until SHADOWFIX_DEPLOY_ROLE_ARN is set, approval reports a dry run.",
  ],
  [
    "Do I need cloud accounts to try it?",
    "No. Empty keys are safe. The demo pipeline, the score, and the dry-run approval all run without Gemini, E2B, AWS, or GitHub credentials.",
  ],
  [
    "When does it open a pull request?",
    "Only when GITHUB_TOKEN, GITHUB_REPOSITORY and SHADOWFIX_OPEN_PR=true are all set. The token comes from the environment, not from a CLI login.",
  ],
  [
    "Can someone point it at any website?",
    "No. Public callers cannot choose a host. The demo target is shopkart://local, and other targets must be registered per tenant.",
  ],
  [
    "How do I run it locally?",
    "Install the backend requirements, start uvicorn on port 8000, then run npm run dev in the frontend folder and open http://127.0.0.1:5183.",
  ],
];

export default function Landing() {
  return (
    <main>
      <Hero />
      <Marquee />
      <Pillars />
      <Agents />
      <HowItRuns />
      <Security />
      <section id="demo" className="scroll-mt-24 px-6 py-24">
        <div className="mx-auto max-w-6xl">
          <SectionHead title="Try the crash yourself." sub="Start a run against the Shopkart sample. The graph updates as each agent finishes." />
          <div className="mt-12">
            <LiveDemo />
          </div>
        </div>
      </section>
      <Faq />
      <FinalCta />
    </main>
  );
}

function Hero() {
  return (
    <section className="glow-top overflow-hidden px-6 pt-20 pb-24 text-center">
      <div className="mx-auto max-w-5xl">
        <a
          href="#demo"
          className="mx-auto inline-flex items-center gap-2 rounded-full border border-line bg-panel/70 px-4 py-1.5 text-[13px] font-semibold text-mute transition-colors hover:border-brand"
        >
          <span className="h-1.5 w-1.5 rounded-full bg-mint" />
          Five agents. One approval. Zero standing keys.
        </a>
        <h1 className="mt-7 text-5xl font-extrabold leading-[1.05] tracking-tight md:text-6xl lg:text-[4.25rem]">
          Agents fix the crash.
          <br />
          Humans approve the deploy.
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-mute">
          ShadowFix reproduces a failing request, names the culprit file, drafts a patch, scores it, and waits. Ship
          repairs at agent speed without giving an agent the keys.
        </p>
        <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
          <Link
            to="/demo"
            className="rounded-full bg-brand px-7 py-3.5 text-sm font-bold text-white shadow-[0_0_40px_-8px_var(--color-brand)] transition-colors hover:bg-brand-deep"
          >
            Run the demo
          </Link>
          <a
            href="https://github.com/shivam9473/shadowfix-ai#readme"
            className="rounded-full border border-line px-7 py-3.5 text-sm font-bold transition-colors hover:border-mint hover:text-mint"
          >
            Read the README
          </a>
        </div>
        <div className="mt-8 flex flex-wrap justify-center gap-2.5 text-[13px] font-semibold text-mute">
          {["Agent graph", "Patch diff", "Eval score", "Admin approval"].map((chip) => (
            <span key={chip} className="rounded-full border border-line bg-panel/60 px-4 py-1.5">
              {chip}
            </span>
          ))}
        </div>
      </div>
      <HeroCard />
    </section>
  );
}

function HeroCard() {
  return (
    <div className="rise mx-auto mt-16 max-w-4xl text-left">
      <div className="card shadow-[0_40px_120px_-30px_rgb(139_92_246/0.55)]">
        <div className="flex items-center justify-between border-b border-line px-5 py-3.5">
          <div className="flex items-center gap-3">
            <span className="flex gap-1.5" aria-hidden="true">
              <i className="h-2.5 w-2.5 rounded-full bg-heat/70" />
              <i className="h-2.5 w-2.5 rounded-full bg-brand/70" />
              <i className="h-2.5 w-2.5 rounded-full bg-mint/70" />
            </span>
            <span className="font-mono text-xs text-mute">incident · tenant shopkart</span>
          </div>
          <span className="rounded-full bg-mint/15 px-3 py-1 text-xs font-bold text-mint">awaiting approval</span>
        </div>
        <div className="grid gap-5 p-5 md:grid-cols-[1.3fr_1fr]">
          <div className="space-y-4">
            <div className="rounded-xl border border-heat/40 bg-heat/10 p-4">
              <div className="flex items-center gap-2 text-xs font-bold text-heat">
                <span className="h-2 w-2 rounded-full bg-heat" /> Critical
              </div>
              <p className="mt-2 text-sm font-bold">ZeroDivisionError in compute_total</p>
              <p className="mt-1 font-mono text-xs text-mute">demo-shopkart/api/checkout.py</p>
              <p className="mt-2 text-sm leading-relaxed text-mute">
                A 100% coupon arrives as discount 1.0 and is used as a divisor.
              </p>
            </div>
            <pre className="overflow-x-auto rounded-xl border border-line bg-ink p-4 font-mono text-xs leading-6">
              <code>
                <span className="block bg-heat/15 text-heat">- return round(subtotal / (1 - discount), 2)</span>
                <span className="block bg-mint/15 text-mint">+ return round(subtotal * (1 - discount), 2)</span>
              </code>
            </pre>
          </div>
          <div className="flex flex-col justify-between gap-4 rounded-xl border border-line bg-ink/60 p-5">
            <div>
              <p className="text-xs font-bold text-mute">Eval score (sample run)</p>
              <p className="mt-2 text-5xl font-extrabold tracking-tight">
                92<span className="text-xl text-mute"> / 85</span>
              </p>
              <div className="mt-4 h-2 overflow-hidden rounded-full bg-line">
                <div className="h-full w-[92%] rounded-full bg-gradient-to-r from-brand to-mint" />
              </div>
              <ul className="mt-4 space-y-1.5 text-sm text-mute">
                <li>✓ Secret scan clean</li>
                <li>✓ Sandbox checked</li>
                <li>✓ Pull request prepared</li>
              </ul>
            </div>
            <Link
              to="/console"
              className="rounded-full bg-paper px-4 py-2.5 text-center text-sm font-bold text-ink transition-colors hover:bg-mint"
            >
              Approve 15-minute deploy
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}

function Marquee() {
  const items = [...STACK, ...STACK];
  return (
    <section className="border-y border-line bg-ink-2 py-7" aria-label="Built with">
      <p className="mb-5 text-center text-xs font-bold text-mute">Built on the tools your platform team already runs</p>
      <div className="marquee overflow-hidden" style={{ maskImage: "linear-gradient(90deg, transparent, #000 12%, #000 88%, transparent)" }}>
        <div className="marquee-track">
          {items.map((name, index) => (
            <span key={`${name}-${index}`} className="mx-8 text-xl font-extrabold tracking-tight text-mute/80 whitespace-nowrap">
              {name}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}

export function SectionHead({ title, sub, id, as: Tag = "h2" }) {
  return (
    <div id={id} className="mx-auto max-w-3xl text-center">
      <Tag className="text-4xl font-extrabold leading-tight tracking-tight md:text-5xl">{title}</Tag>
      {sub && <p className="mt-4 text-lg leading-relaxed text-mute">{sub}</p>}
    </div>
  );
}

function Pillars() {
  return (
    <section className="px-6 py-24">
      <div className="mx-auto max-w-6xl">
        <SectionHead title="Let agents run the desk, with guardrails." sub="Quality control sits inside the loop, so repairs keep pace with the crashes." />
        <div className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {PILLARS.map((item) => (
            <div key={item.title} className="card p-6">
              <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand/15 text-brand">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d={item.icon} />
                </svg>
              </span>
              <h3 className="mt-5 text-lg font-bold leading-snug">{item.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-mute">{item.body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

export function Agents({ page = false }) {
  const Title = page ? "h1" : "h2";
  return (
    <section id="agents" className="scroll-mt-24 border-t border-line bg-ink-2 px-6 py-24">
      <div className="mx-auto grid max-w-6xl items-center gap-14 lg:grid-cols-2">
        <div>
          <p className="text-sm font-bold text-brand">The agent crew</p>
          <Title className="mt-3 text-4xl font-extrabold leading-tight tracking-tight md:text-5xl">
            Five agents, one hand-off at a time.
          </Title>
          <p className="mt-4 text-lg leading-relaxed text-mute">
            LangGraph runs the sequence. The Temporal version waits on an approve signal before the deploy step.
          </p>
          <ol className="mt-9 space-y-6">
            {AGENTS.map((agent) => (
              <li key={agent.name} className="flex gap-5">
                <span className="mt-0.5 font-mono text-sm font-medium text-brand">{agent.n}</span>
                <div>
                  <h3 className="text-lg font-bold">{agent.name}</h3>
                  <p className="mt-1 text-sm leading-relaxed text-mute">{agent.body}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>
        <div className="card dots p-6">
          <p className="text-xs font-bold text-mute">Pipeline</p>
          <div className="mt-5 space-y-3">
            {AGENTS.concat([{ n: "→", name: "Admin approval", body: "" }]).map((agent, index, all) => (
              <div key={agent.name}>
                <div className="flex items-center justify-between rounded-xl border border-line bg-ink/70 px-4 py-3">
                  <span className="text-sm font-bold">{agent.name}</span>
                  <span className={`font-mono text-xs ${index === all.length - 1 ? "text-mint" : "text-mute"}`}>
                    {index === all.length - 1 ? "waits for a human" : "done"}
                  </span>
                </div>
                {index < all.length - 1 && <div className="mx-auto h-4 w-px bg-line" />}
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

export function HowItRuns() {
  const [active, setActive] = useState(0);
  const step = RUN_STEPS[active];
  const tone = { "!": "text-heat", "-": "text-heat", "+": "text-mint", "✓": "text-mint", "$": "text-brand" };
  return (
    <section className="px-6 py-24">
      <div className="mx-auto max-w-6xl">
        <SectionHead title="How a run works." sub="From the first failing request to the approval screen." />
        <div className="mt-10 flex flex-wrap justify-center gap-2" role="tablist" aria-label="Run stages">
          {RUN_STEPS.map((item, index) => (
            <button
              key={item.tab}
              type="button"
              role="tab"
              aria-selected={active === index}
              onClick={() => setActive(index)}
              className={`rounded-full px-5 py-2 text-sm font-bold transition-colors ${
                active === index ? "bg-brand text-white" : "border border-line text-mute hover:text-paper"
              }`}
            >
              {item.tab}
            </button>
          ))}
        </div>
        <div className="card mt-8 grid gap-8 p-8 md:grid-cols-2 md:p-10" role="tabpanel">
          <div className="flex flex-col justify-center">
            <h3 className="text-2xl font-extrabold tracking-tight">{step.title}</h3>
            <p className="mt-3 leading-relaxed text-mute">{step.body}</p>
          </div>
          <pre className="overflow-x-auto rounded-xl border border-line bg-ink p-5 font-mono text-xs leading-7">
            {step.code.map(([mark, text], index) => (
              <code key={index} className="block whitespace-pre">
                <span className={`mr-3 inline-block w-3 ${tone[mark] || "text-mute"}`}>{mark}</span>
                <span className={tone[mark] && mark !== "$" ? tone[mark] : "text-paper"}>{text}</span>
              </code>
            ))}
          </pre>
        </div>
      </div>
    </section>
  );
}

export function Security({ page = false }) {
  return (
    <section id="security" className="scroll-mt-24 border-t border-line bg-ink-2 px-6 py-24">
      <div className="mx-auto max-w-6xl">
        <SectionHead as={page ? "h1" : "h2"} title="Security rules that are enforced, not suggested." sub="Each rule is a code path or a test in the repo, not a policy document." />
        <div className="mt-14 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {RULES.map(([title, body]) => (
            <div key={title} className="card p-6">
              <h3 className="flex items-center gap-2.5 text-lg font-bold">
                <span className="h-2 w-2 rounded-full bg-mint" />
                {title}
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-mute">{body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

export function Faq({ page = false }) {
  return (
    <section id="faq" className="scroll-mt-24 px-6 py-24">
      <div className="mx-auto max-w-3xl">
        <SectionHead as={page ? "h1" : "h2"} title="Questions?" />
        <div className="mt-12 space-y-3">
          {FAQ.map(([q, a]) => (
            <details key={q} className="card group px-6 py-5">
              <summary className="flex cursor-pointer items-center justify-between gap-4 text-left font-bold">
                {q}
                <span className="text-xl text-brand transition-transform group-open:rotate-45" aria-hidden="true">
                  +
                </span>
              </summary>
              <p className="mt-3 text-sm leading-relaxed text-mute">{a}</p>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}

export function FinalCta() {
  return (
    <section className="glow-bottom border-t border-line px-6 py-24 text-center">
      <h2 className="mx-auto max-w-3xl text-4xl font-extrabold leading-tight tracking-tight md:text-5xl">
        Fix faster. Keep the final say.
      </h2>
      <p className="mx-auto mt-4 max-w-xl text-lg text-mute">
        Run the Shopkart incident in under a minute. No cloud accounts needed.
      </p>
      <div className="mt-9 flex flex-wrap justify-center gap-3">
        <Link to="/demo" className="rounded-full bg-brand px-7 py-3.5 text-sm font-bold text-white shadow-[0_0_40px_-8px_var(--color-brand)] transition-colors hover:bg-brand-deep">
          Run the demo
        </Link>
        <Link to="/console" className="rounded-full border border-line px-7 py-3.5 text-sm font-bold transition-colors hover:border-mint hover:text-mint">
          Open the admin console
        </Link>
      </div>
    </section>
  );
}
