import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { api, type InterviewInfo, type Settings as SettingsT, type TextSize, type ThemeMode } from "./api";

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

        <div>
          <YourDay s={s} save={save} />
          <Calendars s={s} save={save} />
          <Interviews />
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

const DAYS: [string, string][] = [
  ["mon", "Mon"],
  ["tue", "Tue"],
  ["wed", "Wed"],
  ["thu", "Thu"],
  ["fri", "Fri"],
  ["sat", "Sat"],
  ["sun", "Sun"],
];

function DayPicker({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  const on = new Set(value.split(",").filter(Boolean));
  const toggle = (d: string) => {
    const next = new Set(on);
    if (next.has(d)) next.delete(d);
    else next.add(d);
    onChange(DAYS.map(([k]) => k).filter((k) => next.has(k)).join(","));
  };
  return (
    <div className="day-picker" role="group" aria-label={label}>
      {DAYS.map(([k, name]) => (
        <button key={k} type="button" className={`chip${on.has(k) ? " is-on" : ""}`} aria-pressed={on.has(k)} onClick={() => toggle(k)}>
          {name}
        </button>
      ))}
    </div>
  );
}

function NumberField({
  label,
  value,
  unit,
  onSave,
}: {
  label: string;
  value: number;
  unit: string;
  onSave: (n: number) => void;
}) {
  const [v, setV] = useState(String(value));
  useEffect(() => setV(String(value)), [value]);
  return (
    <label className="field inline">
      {label}
      <span className="with-unit">
        <input
          className="input short"
          inputMode="numeric"
          value={v}
          onChange={(e) => setV(e.target.value.replace(/\D/g, ""))}
          onBlur={() => v !== String(value) && onSave(Number(v) || 0)}
        />
        <span className="muted">{unit}</span>
      </span>
    </label>
  );
}

function YourDay({ s, save }: { s: SettingsT; save: (p: Partial<SettingsT>, m?: string) => Promise<void> }) {
  return (
    <Section
      title="Your day"
      hint="Myelin plans study blocks around these. Quran goes right after Fajr; everything else after work, or from your start time on days off."
    >
      <div className="time-row">
        <label className="field inline">
          Work starts
          <input className="input" type="time" value={s.work_start} onChange={(e) => e.target.value && save({ work_start: e.target.value })} />
        </label>
        <label className="field inline">
          Work ends
          <input className="input" type="time" value={s.work_end} onChange={(e) => e.target.value && save({ work_end: e.target.value })} />
        </label>
      </div>
      <p className="field-label">Work days</p>
      <DayPicker label="Work days" value={s.work_days} onChange={(v) => save({ work_days: v })} />
      <p className="field-label">Office days (adds your commute)</p>
      <DayPicker label="Office days" value={s.office_days} onChange={(v) => save({ office_days: v })} />
      <div className="time-row">
        <NumberField label="Commute" value={s.commute_minutes} unit="min each way" onSave={(n) => save({ commute_minutes: n })} />
        <NumberField label="Time for each prayer" value={s.prayer_buffer_minutes} unit="min" onSave={(n) => save({ prayer_buffer_minutes: n })} />
        <NumberField label="Stop studying" value={s.study_cutoff_after_isha} unit="min after Isha" onSave={(n) => save({ study_cutoff_after_isha: n })} />
      </div>
    </Section>
  );
}

function Calendars({ s, save }: { s: SettingsT; save: (p: Partial<SettingsT>, m?: string) => Promise<void> }) {
  const [text, setText] = useState(s.calendar_urls);
  return (
    <Section
      title="Calendars"
      hint="Paste a private iCal link, one per line. Events become busy time; Myelin only reads them."
    >
      <textarea
        className="input calendar-links"
        rows={3}
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="https://calendar.google.com/calendar/ical/…/basic.ics"
        spellCheck={false}
      />
      <div className="form-actions">
        <button type="button" className="btn" onClick={() => save({ calendar_urls: text }, "Calendars saved.")}>
          Save calendars
        </button>
      </div>
      <details className="how-to">
        <summary>Where do I find the link?</summary>
        <p>
          <strong>Google Calendar:</strong> on a computer, open Settings, pick your calendar under "Settings for my
          calendars", then copy "Secret address in iCal format".
        </p>
        <p>
          <strong>Outlook:</strong> open Settings, Calendar, Shared calendars, then "Publish a calendar". Choose "Can
          view all details" and copy the ICS link. Some work accounts don't allow this; type "busy 2-4" instead.
        </p>
      </details>
    </Section>
  );
}

function Interviews() {
  const [list, setList] = useState<InterviewInfo[]>([]);
  const [company, setCompany] = useState("");
  const [role, setRole] = useState("");
  const [on, setOn] = useState("");
  const [error, setError] = useState<string | null>(null);
  const load = () => api.interviews().then(setList);
  useEffect(() => {
    load();
  }, []);

  const add = async (e: FormEvent) => {
    e.preventDefault();
    if (!company.trim() || !on) {
      setError("Add the company and the date.");
      return;
    }
    try {
      await api.addInterview({ company, role, on });
      setCompany("");
      setRole("");
      setOn("");
      setError(null);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const fmt = new Intl.DateTimeFormat(undefined, { weekday: "short", month: "short", day: "numeric" });
  return (
    <Section
      title="Interviews"
      hint="Two weeks out, a daily prep block appears. Three days out, it becomes a mock interview."
    >
      {list.length > 0 && (
        <ul className="interview-list">
          {list.map((iv) => (
            <li key={iv.id}>
              <span>
                <strong>{iv.company}</strong>
                {iv.role && <span className="muted">, {iv.role}</span>}
              </span>
              <span className="muted">
                {fmt.format(new Date(`${iv.on}T12:00:00`))}
                {iv.days_left >= 0 ? `, in ${iv.days_left} days` : ", done"}
              </span>
              <button type="button" className="link-button small" onClick={async () => (await api.deleteInterview(iv.id), load())}>
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}
      <form className="interview-form" onSubmit={add}>
        <input className="input" placeholder="Company" value={company} onChange={(e) => setCompany(e.target.value)} />
        <input className="input" placeholder="Role (optional)" value={role} onChange={(e) => setRole(e.target.value)} />
        <input className="input" type="date" value={on} onChange={(e) => setOn(e.target.value)} aria-label="Interview date" />
        <button type="submit" className="btn">
          Add interview
        </button>
      </form>
      {error && <p className="form-error">{error}</p>}
    </Section>
  );
}
