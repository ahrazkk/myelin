import { useEffect, useState, type FormEvent } from "react";
import { api, type Settings as SettingsT } from "./api";

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

export function Settings({ embedded = false }: { embedded?: boolean }) {
  const [s, setS] = useState<SettingsT | null>(null);
  const [lat, setLat] = useState("");
  const [lng, setLng] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [locating, setLocating] = useState(false);

  useEffect(() => {
    api.settings().then((loaded) => {
      setS(loaded);
      setLat(loaded.latitude?.toString() ?? "");
      setLng(loaded.longitude?.toString() ?? "");
    }, (e) => setStatus(e.message));
  }, []);

  const save = async (patch: Partial<SettingsT>) => {
    try {
      const saved = await api.saveSettings({
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        ...patch,
      });
      setS(saved);
      setStatus("Saved. Prayer times update on the wallpaper within a minute.");
    } catch (e) {
      setStatus(e instanceof Error ? e.message : String(e));
    }
  };

  const useMyLocation = () => {
    if (!navigator.geolocation) {
      setStatus("This browser can't share its location. Type your latitude and longitude instead.");
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
        save({ latitude: la, longitude: lo });
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
    save({ latitude: la, longitude: lo });
  };

  const Wrapper = embedded ? "section" : "main";
  return (
    <Wrapper className={embedded ? "settings is-embedded" : "settings"} aria-label={embedded ? "Settings" : undefined}>
      {!embedded && (
        <>
          <a className="back" href="/">Back to today</a>
          <h1>Settings</h1>
        </>
      )}

      <section>
        <h2>Location for prayer times</h2>
        <p className="hint">
          Myelin calculates prayer times on this computer. Your location never leaves it.
        </p>
        <button type="button" className="primary" onClick={useMyLocation} disabled={locating}>
          {locating ? "Finding your location…" : "Use my location"}
        </button>
        <form className="coords" onSubmit={saveTyped}>
          <label>
            Latitude
            <input inputMode="decimal" value={lat} onChange={(e) => setLat(e.target.value)} placeholder="43.65" />
          </label>
          <label>
            Longitude
            <input inputMode="decimal" value={lng} onChange={(e) => setLng(e.target.value)} placeholder="-79.38" />
          </label>
          <button type="submit">Save location</button>
        </form>
      </section>

      {s && (
        <section>
          <h2>Calculation</h2>
          <label className="field">
            Method
            <select value={s.calc_method} onChange={(e) => save({ calc_method: e.target.value })}>
              {METHODS.map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </label>
          <label className="field">
            Asr
            <select value={s.asr_method} onChange={(e) => save({ asr_method: e.target.value })}>
              <option value="SHAFI">Standard (Shafi'i, Maliki, Hanbali)</option>
              <option value="HANAFI">Hanafi</option>
            </select>
          </label>
        </section>
      )}

      {status && <p className="status" role="status">{status}</p>}
    </Wrapper>
  );
}
