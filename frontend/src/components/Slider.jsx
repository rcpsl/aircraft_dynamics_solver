export default function Slider({ label, value, min, max, onChange }) {
  return (
    <div className="slider-row">
      <label>{label}</label>
      <input type="range" min={min} max={max} value={value}
        onChange={e => onChange(Number(e.target.value))} />
      <span className="slider-value">{value}</span>
    </div>
  );
}
