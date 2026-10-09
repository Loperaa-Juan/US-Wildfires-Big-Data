const LOCALE = "es-CO"; // groups every number with a period: 1.878.525

const integer = new Intl.NumberFormat(LOCALE, { maximumFractionDigits: 0 });
const decimal = new Intl.NumberFormat(LOCALE, { maximumFractionDigits: 2 });
const compact = new Intl.NumberFormat(LOCALE, {
  notation: "compact",
  maximumFractionDigits: 1,
});

export const formatInt = (n: number) => integer.format(n);
export const formatNumber = (n: number) => decimal.format(n);
/** 1.878.525 -> "1,9 M", 12.900 -> "12,9 mil". */
export const formatCompact = (n: number) => compact.format(n);

export function formatHour(hour: number): string {
  return `${String(hour).padStart(2, "0")}:00`;
}

/** "-120.75, 40.25" as "40,25° N · 120,75° O". */
export function formatLonLat([lon, lat]: [number, number]): string {
  const ns = lat >= 0 ? "N" : "S";
  const ew = lon >= 0 ? "E" : "O"; // Oeste
  return `${formatNumber(Math.abs(lat))}° ${ns} · ${formatNumber(Math.abs(lon))}° ${ew}`;
}

/** "2005-02-02" -> "2 feb 2005". Dates are UTC midnights, so they are read in UTC. */
export function formatDate(iso: string): string {
  const date = new Date(iso);
  const month = MONTHS[date.getUTCMonth()].toLowerCase();
  return `${date.getUTCDate()} ${month} ${date.getUTCFullYear()}`;
}

// The Spark results keep the dataset's English labels; the UI shows them in Spanish.
const WEEKDAYS: Record<string, string> = {
  Sunday: "Dom",
  Monday: "Lun",
  Tuesday: "Mar",
  Wednesday: "Mié",
  Thursday: "Jue",
  Friday: "Vie",
  Saturday: "Sáb",
};
const MONTHS = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];

export const CAUSES: Record<string, string> = {
  "Debris Burning": "Quema de residuos",
  Miscellaneous: "Varios",
  Arson: "Provocado",
  Lightning: "Rayo",
  "Missing/Undefined": "Sin dato",
  "Equipment Use": "Uso de equipos",
  Campfire: "Fogata",
  Children: "Niños",
  Smoking: "Fumadores",
  Railroad: "Ferrocarril",
  Powerline: "Tendido eléctrico",
  Fireworks: "Pirotecnia",
  Structure: "Estructura",
};

export const weekdayLabel = (name: string) => WEEKDAYS[name] ?? name;
export const monthLabel = (month: number) => MONTHS[month - 1] ?? String(month);
export const causeLabel = (cause: string) => CAUSES[cause] ?? cause;
