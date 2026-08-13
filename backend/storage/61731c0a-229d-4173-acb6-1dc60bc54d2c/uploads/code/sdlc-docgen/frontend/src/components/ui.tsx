import { useEffect, useState, type CSSProperties, type ReactNode } from "react";

/* ---------------- Icons (inline SVG, stroke-based) ---------------- */

const PATHS: Record<string, ReactNode> = {
  shield: (
    <>
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      <path d="M9 12l2 2 4-4" />
    </>
  ),
  file: (
    <>
      <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" />
      <path d="M13 2v7h7" />
    </>
  ),
  filetext: (
    <>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <path d="M14 2v6h6" />
      <path d="M16 13H8M16 17H8M10 9H8" />
    </>
  ),
  upload: (
    <>
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <path d="M17 8l-5-5-5 5" />
      <path d="M12 3v12" />
    </>
  ),
  download: (
    <>
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <path d="M7 10l5 5 5-5" />
      <path d="M12 15V3" />
    </>
  ),
  check: <path d="M20 6L9 17l-5-5" />,
  x: <path d="M18 6L6 18M6 6l12 12" />,
  checkCircle: (
    <>
      <circle cx="12" cy="12" r="10" />
      <path d="M8.5 12.5l2.5 2.5 4.5-5" />
    </>
  ),
  xCircle: (
    <>
      <circle cx="12" cy="12" r="10" />
      <path d="M15 9l-6 6M9 9l6 6" />
    </>
  ),
  alert: (
    <>
      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
      <path d="M12 9v4M12 17h.01" />
    </>
  ),
  info: (
    <>
      <circle cx="12" cy="12" r="10" />
      <path d="M12 16v-4M12 8h.01" />
    </>
  ),
  chevronLeft: <path d="M15 18l-6-6 6-6" />,
  chevronRight: <path d="M9 18l6-6-6-6" />,
  chevronDown: <path d="M6 9l6 6 6-6" />,
  arrowLeft: <path d="M19 12H5M12 19l-7-7 7-7" />,
  arrowRight: <path d="M5 12h14M12 5l7 7-7 7" />,
  external: (
    <>
      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
      <path d="M15 3h6v6M10 14L21 3" />
    </>
  ),
  search: (
    <>
      <circle cx="11" cy="11" r="8" />
      <path d="M21 21l-4.35-4.35" />
    </>
  ),
  refresh: (
    <>
      <path d="M21 2v6h-6" />
      <path d="M3 12a9 9 0 0 1 15-6.7L21 8" />
      <path d="M3 22v-6h6" />
      <path d="M21 12a9 9 0 0 1-15 6.7L3 16" />
    </>
  ),
  layers: (
    <>
      <path d="M12 2L2 7l10 5 10-5-10-5z" />
      <path d="M2 17l10 5 10-5" />
      <path d="M2 12l10 5 10-5" />
    </>
  ),
  flask: (
    <>
      <path d="M10 2v7L4.6 17.2A2 2 0 0 0 6.4 20h11.2a2 2 0 0 0 1.8-2.8L14 9V2" />
      <path d="M9 2h6M7.5 14h9" />
    </>
  ),
  activity: <path d="M22 12h-4l-3 9L9 3l-3 9H2" />,
  folder: <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />,
  code: <path d="M16 18l6-6-6-6M8 6l-6 6 6 6" />,
  link: (
    <>
      <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
      <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
    </>
  ),
  sparkles: (
    <path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9L12 3zM19 15l.9 2.1L22 18l-2.1.9L19 21l-.9-2.1L16 18l2.1-.9L19 15z" />
  ),
  send: (
    <>
      <path d="M22 2L11 13" />
      <path d="M22 2l-7 20-4-9-9-4 20-7z" />
    </>
  ),
  plus: <path d="M12 5v14M5 12h14" />,
  sliders: (
    <>
      <path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6" />
    </>
  ),
  list: (
    <>
      <path d="M8 6h13M8 12h13M8 18h13" />
      <path d="M3 6h.01M3 12h.01M3 18h.01" />
    </>
  ),
  database: (
    <>
      <ellipse cx="12" cy="5" rx="9" ry="3" />
      <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
      <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
    </>
  ),
  cpu: (
    <>
      <rect x="4" y="4" width="16" height="16" rx="2" />
      <path d="M9 2v2M15 2v2M9 20v2M15 20v2M2 9h2M2 15h2M20 9h2M20 15h2" />
      <rect x="9" y="9" width="6" height="6" />
    </>
  ),
  target: (
    <>
      <circle cx="12" cy="12" r="10" />
      <circle cx="12" cy="12" r="6" />
      <circle cx="12" cy="12" r="2" />
    </>
  ),
  clock: (
    <>
      <circle cx="12" cy="12" r="10" />
      <path d="M12 6v6l4 2" />
    </>
  ),
  git: (
    <>
      <circle cx="6" cy="6" r="3" />
      <circle cx="6" cy="18" r="3" />
      <path d="M6 9v6M6 9a9 9 0 0 0 9 9" />
    </>
  ),
  rocket: (
    <>
      <path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z" />
      <path d="M12 15l-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z" />
      <path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5" />
    </>
  ),
  key: (
    <>
      <circle cx="7.5" cy="15.5" r="5.5" />
      <path d="M21 2l-9.6 9.6M15.5 7.5l3 3L22 7l-3-3" />
    </>
  ),
  scale: (
    <>
      <path d="M12 3v18M5 7h14" />
      <path d="M5 7l-3 6a3 3 0 0 0 6 0L5 7zM19 7l-3 6a3 3 0 0 0 6 0l-3-6z" />
    </>
  ),
};

export function Icon({ name, size = 18, className }: { name: keyof typeof PATHS; size?: number; className?: string }) {
  return (
    <svg
      className={`icon ${className || ""}`}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {PATHS[name]}
    </svg>
  );
}

/* ---------------- Chips ---------------- */

const CHIP_TONES = {
  neutral: "chip",
  green: "chip chip-green",
  amber: "chip chip-amber",
  red: "chip chip-red",
  cyan: "chip chip-cyan",
  violet: "chip chip-violet",
  teal: "chip chip-teal",
} as const;

export function Chip({
  tone = "neutral",
  children,
  dot,
  title,
}: {
  tone?: keyof typeof CHIP_TONES;
  children: ReactNode;
  dot?: boolean;
  title?: string;
}) {
  return (
    <span className={CHIP_TONES[tone]} title={title}>
      {dot && <span className="dot" />}
      {children}
    </span>
  );
}

/* ---------------- Buttons ---------------- */

const BTN_VARIANTS = {
  primary: "btn btn-primary",
  ghost: "btn btn-ghost",
  danger: "btn btn-danger",
  success: "btn btn-success",
  solid: "btn",
} as const;

export function Button({
  variant = "solid",
  size,
  icon,
  children,
  className,
  ...props
}: {
  variant?: keyof typeof BTN_VARIANTS;
  size?: "sm" | "icon";
  icon?: keyof typeof PATHS;
  children?: ReactNode;
  className?: string;
} & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  const sizeClass = size === "sm" ? "btn-sm" : size === "icon" ? "btn-icon" : "";
  return (
    <button className={`${BTN_VARIANTS[variant]} ${sizeClass} ${className || ""}`} {...props}>
      {icon && <Icon name={icon} size={15} />}
      {children}
    </button>
  );
}

/* ---------------- Card ---------------- */

export function Card({
  title,
  icon,
  right,
  children,
  hover,
  className,
  style,
  onClick,
}: {
  title?: ReactNode;
  icon?: keyof typeof PATHS;
  right?: ReactNode;
  children: ReactNode;
  hover?: boolean;
  className?: string;
  style?: CSSProperties;
  onClick?: () => void;
}) {
  return (
    <div
      className={`card ${hover ? "card-hover" : ""} ${className || ""}`}
      style={style}
      onClick={onClick}
    >
      {(title || right) && (
        <div className="row" style={{ justifyContent: "space-between", marginBottom: 14 }}>
          <h3 className="card-title">
            {icon && <Icon name={icon} />}
            {title}
          </h3>
          {right}
        </div>
      )}
      {children}
    </div>
  );
}

/* ---------------- Stat ---------------- */

export function Stat({
  icon,
  value,
  label,
  tone = "cyan",
}: {
  icon: keyof typeof PATHS;
  value: ReactNode;
  label: ReactNode;
  tone?: "cyan" | "green" | "amber" | "violet" | "teal" | "red";
}) {
  const iconStyle: Record<string, CSSProperties> = {
    cyan: { background: "var(--accent-soft)", color: "var(--accent)" },
    green: { background: "var(--success-soft)", color: "var(--success)" },
    amber: { background: "var(--warning-soft)", color: "var(--warning)" },
    violet: { background: "rgba(167,139,250,0.12)", color: "var(--violet)" },
    teal: { background: "rgba(45,212,191,0.12)", color: "var(--teal)" },
    red: { background: "var(--danger-soft)", color: "var(--danger)" },
  };
  return (
    <div className="stat">
      <div className="stat-icon" style={iconStyle[tone]}>
        <Icon name={icon} size={20} />
      </div>
      <div>
        <div className="stat-value">{value}</div>
        <div className="stat-label">{label}</div>
      </div>
    </div>
  );
}

/* ---------------- Progress ---------------- */

export function Progress({
  value,
  max = 1,
  tone = "cyan",
}: {
  value: number;
  max?: number;
  tone?: "cyan" | "green" | "amber";
}) {
  const pct = Math.max(0, Math.min(100, (value / (max || 1)) * 100));
  const cls = tone === "green" ? "progress progress-green" : tone === "amber" ? "progress progress-amber" : "progress";
  return (
    <div className={cls} title={`${pct.toFixed(0)}%`}>
      <span style={{ width: `${pct}%` }} />
    </div>
  );
}

/* ---------------- Misc ---------------- */

export function Spinner({ large }: { large?: boolean }) {
  return <span className={`spinner ${large ? "spinner-lg" : ""}`} />;
}

export function Alert({
  tone,
  children,
}: {
  tone: "info" | "error" | "success";
  children: ReactNode;
}) {
  return <div className={`alert alert-${tone}`}>{children}</div>;
}

export function EmptyState({ icon, title, body }: { icon: keyof typeof PATHS; title: string; body?: ReactNode }) {
  return (
    <div className="empty-state">
      <span className="es-icon">
        <Icon name={icon} size={38} />
      </span>
      <strong style={{ fontSize: 15 }}>{title}</strong>
      {body && <div className="muted" style={{ fontSize: 13 }}>{body}</div>}
    </div>
  );
}

/* ---------------- Toasts ---------------- */

type ToastTone = "info" | "success" | "error";

interface ToastItem {
  id: number;
  tone: ToastTone;
  text: string;
}

let nextToastId = 0;
const toastListeners = new Set<(item: ToastItem) => void>();

export function toast(text: string, tone: ToastTone = "info") {
  const item = { id: ++nextToastId, tone, text };
  toastListeners.forEach((listener) => listener(item));
}

export function ToastHost() {
  const [items, setItems] = useState<ToastItem[]>([]);

  useEffect(() => {
    const listener = (item: ToastItem) => setItems((prev) => [...prev, item]);
    toastListeners.add(listener);
    return () => {
      toastListeners.delete(listener);
    };
  }, []);

  useEffect(() => {
    if (items.length === 0) return;
    const timer = setTimeout(() => setItems((prev) => prev.slice(1)), 4200);
    return () => clearTimeout(timer);
  }, [items]);

  return (
    <div className="toast-host">
      {items.map((item) => (
        <div key={item.id} className={`toast toast-${item.tone}`} onClick={() => setItems((prev) => prev.filter((t) => t.id !== item.id))}>
          <Icon name={item.tone === "success" ? "checkCircle" : item.tone === "error" ? "xCircle" : "info"} size={16} />
          <span>{item.text}</span>
        </div>
      ))}
    </div>
  );
}
