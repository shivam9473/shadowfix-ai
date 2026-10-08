import { useState } from "react";

const PRODUCTS = [
  { sku: "lamp", name: "Desk lamp", price: 1200 },
  { sku: "mug", name: "Clay mug", price: 450 },
  { sku: "notebook", name: "Grid notebook", price: 220 },
];

export default function App() {
  const [coupon, setCoupon] = useState("");
  const [result, setResult] = useState("");

  async function pay() {
    setResult("Charging…");
    const discount = coupon.trim().toUpperCase() === "SHADOW" ? 1 : 0;
    try {
      const response = await fetch("/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          items: PRODUCTS.map((item) => ({ ...item, qty: 1 })),
          discount,
        }),
      });
      const text = await response.text();
      setResult(response.ok ? `Charged ${JSON.parse(text).total}` : text);
    } catch (err) {
      setResult(err.message);
    }
  }

  return (
    <main className="mx-auto max-w-xl px-6 py-12">
      <p className="text-xs tracking-[0.2em]">SHOPKART</p>
      <h1 className="mt-2 text-4xl">A small counter.</h1>
      <ul className="mt-8 divide-y divide-neutral-300">
        {PRODUCTS.map((item) => (
          <li key={item.sku} className="flex justify-between py-3">
            <span>{item.name}</span>
            <span>₹{item.price}</span>
          </li>
        ))}
      </ul>
      <label className="mt-6 block text-sm">
        Coupon
        <input
          value={coupon}
          onChange={(event) => setCoupon(event.target.value)}
          placeholder="SHADOW"
          className="mt-2 w-full border border-neutral-400 bg-transparent px-3 py-2"
        />
      </label>
      <button type="button" id="pay" onClick={pay} className="mt-4 bg-neutral-900 px-4 py-2 text-sm text-white">
        Pay now
      </button>
      {result && <pre className="mt-6 whitespace-pre-wrap text-sm">{result}</pre>}
    </main>
  );
}
