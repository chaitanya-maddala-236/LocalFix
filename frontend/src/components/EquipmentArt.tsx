export function EquipmentArt({ compact = false }: { compact?: boolean }) {
  return <svg className={`equipment-art ${compact ? 'equipment-art-compact' : ''}`} viewBox="0 0 860 530" role="img" aria-label="Original synthetic illustration of a DemoTech ACM-4200 motor controller">
    <defs>
      <linearGradient id="cabinet" x1="0" x2="1"><stop stopColor="#3b4140"/><stop offset=".48" stopColor="#252a29"/><stop offset="1" stopColor="#171b1a"/></linearGradient>
      <linearGradient id="door" x1="0" x2="0.9"><stop stopColor="#343a39"/><stop offset="1" stopColor="#1d2221"/></linearGradient>
      <linearGradient id="panel" x1="0" x2="1"><stop stopColor="#131817"/><stop offset="1" stopColor="#080c0b"/></linearGradient>
      <filter id="shadow"><feGaussianBlur stdDeviation="18"/></filter>
      <pattern id="grain" width="10" height="10" patternUnits="userSpaceOnUse"><path d="M0 9h10" stroke="#fff" strokeOpacity=".018"/></pattern>
    </defs>
    <ellipse cx="432" cy="479" rx="263" ry="27" fill="#000" opacity=".55" filter="url(#shadow)"/>
    <g transform="translate(180 32)">
      <path d="M58 14h414l30 25v392l-26 28H48l-22-22V38z" fill="url(#cabinet)" stroke="#69716f" strokeOpacity=".65" strokeWidth="2"/>
      <path d="M48 25h387v396H48z" fill="url(#door)" stroke="#59615f" strokeOpacity=".5"/>
      <path d="M48 25h387v396H48z" fill="url(#grain)"/>
      <path d="M435 25l45 17v377l-45 2z" fill="#1c211f" stroke="#69716f" strokeOpacity=".4"/>
      <path d="M445 59h20v320h-20" fill="none" stroke="#0b0e0d" strokeWidth="7"/>
      <circle cx="453" cy="206" r="8" fill="#707876"/><circle cx="453" cy="206" r="3" fill="#1b201f"/>
      <rect x="92" y="61" width="219" height="124" rx="8" fill="url(#panel)" stroke="#626a68" strokeOpacity=".7"/>
      <rect x="111" y="81" width="92" height="53" rx="5" fill="#070b0a" stroke="#4b5551"/>
      <text x="157" y="117" textAnchor="middle" fill="#f2b76c" fontFamily="monospace" fontSize="27" letterSpacing="4">E07</text>
      <circle cx="228" cy="95" r="7" fill="#bf573e"/><circle cx="253" cy="95" r="7" fill="#c7ee6b"/>
      <text x="228" y="117" textAnchor="middle" fill="#a7ada9" fontFamily="sans-serif" fontSize="8">FAULT</text>
      <text x="253" y="117" textAnchor="middle" fill="#a7ada9" fontFamily="sans-serif" fontSize="8">RUN</text>
      <rect x="222" y="143" width="64" height="18" rx="4" fill="#202726" stroke="#515a57"/>
      <circle cx="230" cy="152" r="3" fill="#c8f169"/><circle cx="242" cy="152" r="3" fill="#8d9491"/><circle cx="254" cy="152" r="3" fill="#8d9491"/>
      <text x="111" y="158" fill="#747d79" fontFamily="monospace" fontSize="8" letterSpacing="1.3">DEMOtech  /  ACM-4200</text>
      <rect x="93" y="212" width="219" height="153" rx="5" fill="#202624" stroke="#515957"/>
      <rect x="111" y="229" width="78" height="66" rx="3" fill="#333a37" stroke="#59625e"/>
      <rect x="205" y="226" width="83" height="57" rx="6" fill="#111716" stroke="#6a746f" strokeWidth="2"/>
      <rect x="215" y="237" width="63" height="35" rx="3" fill="#252d2a" stroke="#3e4944"/>
      <text x="247" y="258" textAnchor="middle" fill="#c8f169" fontFamily="monospace" fontSize="10">K2</text>
      <circle cx="247" cy="268" r="2.5" fill="#c8f169"/>
      <rect x="202" y="308" width="78" height="27" rx="4" fill="#131918" stroke="#78817d"/>
      <path d="M213 308v27m13-27v27m13-27v27m13-27v27m13-27v27" stroke="#737d78" strokeWidth="3"/>
      <rect x="109" y="311" width="42" height="34" rx="3" fill="#131918" stroke="#78817d"/>
      <path d="M119 319v18m10-18v18m10-18v18" stroke="#c2a363" strokeWidth="3"/>
      <path d="M139 188v-12h103v12m-103 0v20m103-20v20" fill="none" stroke="#78827e" strokeWidth="2"/>
      <rect x="328" y="72" width="78" height="69" rx="4" fill="#222826" stroke="#606966"/>
      <text x="367" y="92" textAnchor="middle" fill="#a7b0ac" fontFamily="monospace" fontSize="8">IDENTIFICATION</text>
      <text x="367" y="111" textAnchor="middle" fill="#e2e7e3" fontFamily="monospace" fontSize="10">ACM-4200</text>
      <text x="367" y="127" textAnchor="middle" fill="#9ca5a1" fontFamily="monospace" fontSize="8">SN-823919</text>
      <rect x="336" y="222" width="61" height="79" rx="4" fill="#292f2d" stroke="#59625f"/>
      <path d="M349 236h35m-35 12h35m-35 12h35m-35 12h35" stroke="#727b77" strokeWidth="3"/>
      <path d="M80 439h370m-353 0v13m335-13v13" stroke="#707a76" strokeWidth="5"/>
      <path d="M36 57h8m-8 12h8m-8 12h8m442-24h9m-9 12h9m-9 12h9" stroke="#77807d" strokeOpacity=".6"/>
    </g>
  </svg>
}
