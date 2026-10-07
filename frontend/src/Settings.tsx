import { useState, type FormEvent, type ReactNode } from "react";
import type { Settings as SettingsT, TextSize, ThemeMode } from "./api";

const METHODS: [string, string][] = [
  ["NORTH_AMERICA", "ISNA (North America)"],
  ["MUSLIM_WORLD_LEAGUE", "Muslim World League"],
  ["MOON_SIGHTING_COMMITTEE", "Moonsighting Committee"],
  ["UMM_AL_QURA", "Umm al-Qura, Makkah"],
  ["EGYPTIAN", "Egyptian General Authority"],
  ["KARACHI", "University of Islamic Sciences, Karachi"],
  ["DUBAI", "Gulf region"],
  ["KUWAIT", "Kuwait"],
  ["QATAR", "Qatar"],
  ["SINGAPORE", "Singapore"],
  ["UOIF", "UOIF (France)"],
];

const THEMES: [ThemeMode, string][] = [
  ["auto", "Auto"],
  ["light", "Light"],
  ["dark", "Dark"],
  ["system", "Follow Windows"],
];

const SIZES: [TextSize, string][] = [
  ["normal", "Normal"],
  ["large", "Large"],
  ["larger", "Larger"],
];

export type SaveSettings = (patch: Partial<SettingsT>) => Promise<void>;

export function Segmented<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T;
  options: [T, string][];
  onChange: (v: T) => void;
}) {
  return (
    <div className="segmented" role="radiogroup" aria-label={label}>
      {options.map(([v, text]) => (
        <button key={v} type="button" role="radio" aria-checked={value === v} onClick={() => onChange(v)}>
          {text}
        </button>
      ))}
    </div>
  );
}

function Section({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  return (
    <section className="settings-section">
      <h2>{title}</h2>
      {hint && <p className="hint">{hint}</p>}
      {children}
    </section>
  );
}

export function Settings({ settings: s, onSave }: { settings: SettingsT; onSave: SaveSettings }) {
  const [lat, setLat] = useState(s.latitude?.toString() ?? "");
  const [lng, setLng] = useState(s.longitude?.toString() ?? "");
  const [status, setStatus] = useState<string | null>(null);
  const [locating, setLocating] = useState(false);

  const save = async (patch: Partial<SettingsT>, message = "Saved.") => {
    try {
      await onSave(patch);
      setStatus(message);
    } catch (e) {
      setStatus(e instanceof Error ? e.message : String(e));
    }
  };

  const useMyLocation = () => {
    if (!navigator.geolocation) {
      setStatus("This window can't share its location. Type your latitude and longitude instead.");
      return;
    }
    setLocating(true);
    setStatus(null);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        // Two decimals is about 1 km: plenty for prayer times, and it keeps your exact address out of the app.
        const la = Math.round(pos.coords.latitude * 100) / 100;
        const lo = Math.round(pos.coords.longitude * 100) / 100;
        setLat(la.toString());
        setLng(lo.toString());
        setLocating(false);
        save({ latitude: la, longitude: lo }, "Location saved. Prayer times are on Today.");
      },
      () => {
        setLocating(false);
        setStatus("Location was blocked. Type your latitude and longitude instead; a maps app shows both.");
      },
      { timeout: 15000 },
    );
  };

  const saveTyped = (e: FormEvent) => {
    e.preventDefault();
    const la = Number(lat);
    const lo = Number(lng);
    if (!lat || !lng || Number.isNaN(la) || Number.isNaN(lo) || Math.abs(la) > 90 || Math.abs(lo) > 180) {
      setStatus("Latitude must be between -90 and 90, longitude between -180 and 180.");
      return;
    }
    save({ latitude: la, longitude: lo }, "Location saved. Prayer times are on Today.");
  };

  return (
    <section className="settings" aria-label="Settings">
      <div className="settings-columns">
        <div>
          <Section title="Appearance" hint="Auto switches to the night view at Maghrib and back at sunrise.">
            <Segmented label="Theme" value={s.theme} options={THEMES} onChange={(v) => save({ theme: v })} />
            <p className="field-label">Text size</p>
            <Segmented label="Text size" value={s.text_size} options={SIZES} onChange={(v) => save({ text_size: v })} />
            <label className="check-field">
              <input
                type="checkbox"
                checked={s.reduced_motion}
                onChange={(e) => save({ reduced_motion: e.target.checked })}
              />
              Reduce motion
            </label>
          </Section>

          <Section
            title="Location for prayer times"
            hint="Myelin calculates prayer times on this computer. Your location never leaves it."
          >
            <button type="button" className="btn primary" onClick={useMyLocation} disabled={locating}>
              {locating ? "Finding your location…" : "Use my location"}
            </button>
            <form className="coords" onSubmit={saveTyped}>
              <label>
                Latitude
                <input className="input" inputMode="decimal" value={lat} onChange={(e) => setLat(e.target.value)} placeholder="43.65" />
              </label>
              <label>
                Longitude
                <input className="input" inputMode="decimal" value={lng} onChange={(e) => setLng(e.target.value)} placeholder="-79.38" />
              </label>
              <button type="submit" className="btn">
                Save location
              </button>
            </form>
          </Section>

          <Section title="Calculation">
            <label className="field">
              Method
              <select className="input" value={s.calc_method} onChange={(e) => save({ calc_method: e.target.value })}>
                {METHODS.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              Asr
              <select className="input" value={s.asr_method} onChange={(e) => save({ asr_method: e.target.value })}>
                <option value="SHAFI">Standard (Shafi'i, Maliki, Hanbali)</option>
                <option value="HANAFI">Hanafi</option>
              </select>
            </label>
          </Section>
        </div>
      </div>

      {status && (
        <p className="status" role="status">
          {status}
        </p>
      )}
    </section>
  );
}
