import Slider from '../Slider';

export default function NoiseModelTab({ dbPerCraft, setDbPerCraft }) {
  return (
    <div>
      <section>
        <h2>Aircraft Noise</h2>
        <Slider label="dB / aircraft" value={dbPerCraft} min={40} max={80} onChange={setDbPerCraft} />
        <p className="noise-model-desc">
          Noise each aircraft adds at a station. Combined with the
          station's zone baseline using:<br />
          10 · log₁₀( 10^(baseline/10) + n · 10^(dB/10) )
        </p>
      </section>
    </div>
  );
}
