import LiveDemo from "../components/LiveDemo";

export default function PublicDemo() {
  return (
    <main className="glow-top">
      <div className="mx-auto max-w-6xl px-6 py-14">
        <h1 className="max-w-3xl text-4xl font-extrabold leading-tight tracking-tight md:text-5xl">
          Reproduce the crash. Name the file. Wait for approval.
        </h1>
        <p className="mt-4 max-w-2xl leading-relaxed text-mute">
          This demo runs the Shopkart checkout. Coupon SHADOW is a 100% discount implemented as a divisor, so the API
          raises ZeroDivisionError. Five agents diagnose it. Nothing is deployed until an admin approves.
        </p>
        <div className="mt-10">
          <LiveDemo />
        </div>
      </div>
    </main>
  );
}
