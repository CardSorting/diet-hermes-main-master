/** Decorative soda-can silhouette with animated fizz + pour (parody aesthetic). */

export function SodaCanVisual({ className = "" }: { className?: string }) {
  return (
    <svg
      className={`dc-can-svg ${className}`}
      viewBox="0 0 64 128"
      role="img"
      aria-label="DietCode soda can"
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        <linearGradient id="dc-can-body" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#ff4d6a" />
          <stop offset="45%" stopColor="#e31837" />
          <stop offset="100%" stopColor="#9b0f24" />
        </linearGradient>
        <linearGradient id="dc-can-silver" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="#f5f5f7" />
          <stop offset="100%" stopColor="#a8adb8" />
        </linearGradient>
        <linearGradient id="dc-pour-stream" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="#ffe8ec" stopOpacity="0.9" />
          <stop offset="100%" stopColor="#ff4d6a" stopOpacity="0.2" />
        </linearGradient>
      </defs>
      {/* Pour stream (animated dash) */}
      <path
        className="dc-can-pour"
        d="M32 0 L32 18"
        stroke="url(#dc-pour-stream)"
        strokeWidth="3"
        strokeLinecap="round"
        fill="none"
      />
      {/* Tab */}
      <rect
        className="dc-can-tab-svg"
        x="22"
        y="10"
        width="20"
        height="8"
        rx="2"
        fill="url(#dc-can-silver)"
      />
      {/* Neck */}
      <path
        d="M20 18 h24 l-2 10 H22 Z"
        fill="url(#dc-can-silver)"
        opacity="0.9"
      />
      {/* Body */}
      <rect x="14" y="28" width="36" height="88" rx="6" fill="url(#dc-can-body)" />
      {/* Highlight stripe */}
      <rect
        x="18"
        y="44"
        width="4"
        height="56"
        rx="2"
        fill="rgba(255,255,255,0.28)"
      />
      {/* Word band */}
      <rect
        x="16"
        y="58"
        width="32"
        height="30"
        rx="2"
        fill="rgba(255,255,255,0.14)"
      />
      <text
        x="32"
        y="74"
        textAnchor="middle"
        fill="#fff5f7"
        fontSize="7"
        fontWeight="700"
        fontFamily="Impact, sans-serif"
        letterSpacing="0.08em"
      >
        DIET
      </text>
      <text
        x="32"
        y="82"
        textAnchor="middle"
        fill="#ffe8ec"
        fontSize="6"
        fontWeight="700"
        fontFamily="Impact, sans-serif"
      >
        CODE
      </text>
      <text
        x="32"
        y="90"
        textAnchor="middle"
        fill="rgba(255,255,255,0.55)"
        fontSize="4"
        fontFamily="sans-serif"
      >
        0 CAL DIFFS
      </text>
      {/* Fizz dots — rising cluster */}
      {[0, 1, 2, 3, 4, 5, 6].map((i) => (
        <circle
          key={i}
          className="dc-can-fizz-dot"
          cx={20 + (i % 4) * 5}
          cy={22 - Math.floor(i / 4) * 3}
          r={1 + (i % 3) * 0.35}
          fill="rgba(255,255,255,0.75)"
          style={{ animationDelay: `${i * 0.28}s` }}
        />
      ))}
      {/* Base shadow */}
      <ellipse cx="32" cy="118" rx="18" ry="4" fill="rgba(0,0,0,0.35)" />
    </svg>
  );
}
