const GRADIENTS: [string, string][] = [
  ["#0a66c2", "#4ea3f1"],
  ["#057642", "#3fbf86"],
  ["#c2410c", "#fb923c"],
  ["#7c3aed", "#c084fc"],
  ["#b45309", "#facc15"],
  ["#0e7490", "#5eead4"],
  ["#be185d", "#f9a8d4"],
];

function gradientFor(seed: string): [string, string] {
  let hash = 0;
  for (const ch of seed) hash = (hash * 31 + ch.charCodeAt(0)) | 0;
  return GRADIENTS[Math.abs(hash) % GRADIENTS.length];
}

/** A soft per-member banner background, matching their avatar colours. */
export function bannerStyle(seed: string): { background: string } {
  const [a, b] = gradientFor(seed);
  return {
    background: `radial-gradient(circle at 85% 20%, ${b}66 0, transparent 45%), linear-gradient(120deg, ${a}cc, ${b}99)`,
  };
}

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join("");
}

export function Avatar({ name, id, size = 48 }: { name: string; id: string; size?: number }) {
  const [a, b] = gradientFor(id);
  return (
    <span
      className="avatar"
      style={{
        width: size,
        height: size,
        fontSize: size * 0.38,
        background: `linear-gradient(135deg, ${a}, ${b})`,
      }}
      aria-hidden="true"
    >
      {initials(name)}
    </span>
  );
}
