// Original ShadowFix mark: a ghost-shaped shadow with a mint "fix" spark as its eye.
export function LogoMark({ size = 28 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden="true">
      <defs>
        <linearGradient id="sf-g" x1="4" y1="2" x2="28" y2="30" gradientUnits="userSpaceOnUse">
          <stop stopColor="#a78bfa" />
          <stop offset="1" stopColor="#6d3df0" />
        </linearGradient>
      </defs>
      <path
        d="M16 2.5c-5.8 0-10 4.3-10 10v15.2c0 .9 1 1.4 1.7.8l2.6-2.2c.4-.3.9-.3 1.3 0l2.5 2.1c.5.4 1.2.4 1.7 0l2.5-2.1c.4-.3.9-.3 1.3 0l2.6 2.2c.7.6 1.8.1 1.8-.8V12.5c0-5.7-4.2-10-10-10Z"
        fill="url(#sf-g)"
      />
      <circle cx="12.3" cy="13.2" r="1.7" fill="#0a0816" />
      <path d="M19.6 10.6v5.2M17 13.2h5.2" stroke="#5eead4" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

export default function Logo() {
  return (
    <span className="flex items-center gap-2.5">
      <LogoMark />
      <span className="text-[17px] font-extrabold tracking-tight">ShadowFix</span>
    </span>
  );
}
