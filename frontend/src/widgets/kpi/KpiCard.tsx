type Props = {
  label: string;
  value: string;
  hint?: string;
  accent?: "blue" | "cyan" | "amber";
};

export default function KpiCard({
  label,
  value,
  hint,
  accent = "blue",
}: Props) {
  return (
    <div className={`kpi-card kpi-card--${accent}`}>
      <div className="kpi-card__topline" />
      <div className="kpi-card__label">{label}</div>
      <div className="kpi-card__value">{value}</div>
      {hint ? <div className="kpi-card__hint">{hint}</div> : null}
    </div>
  );
}