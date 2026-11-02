import { Agents, Faq, FinalCta, HowItRuns, Security } from "./Landing";

export function AgentsPage() {
  return (
    <main>
      <Agents page />
      <HowItRuns />
      <FinalCta />
    </main>
  );
}

export function SecurityPage() {
  return (
    <main>
      <Security page />
      <FinalCta />
    </main>
  );
}

export function FaqPage() {
  return (
    <main>
      <Faq page />
      <FinalCta />
    </main>
  );
}
