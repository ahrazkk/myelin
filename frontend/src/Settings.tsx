import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import {
  api,
  type AppInfo,
  type InterviewInfo,
  type LockScreenStatus,
  type Settings as SettingsT,
  type TextSize,
  type ThemeMode,
} from "./api";

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

          <AppSection s={s} save={save} />

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
          <LockScreens s={s} save={save} />
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

function AppSection({ s, save }: { s: SettingsT; save: (p: Partial<SettingsT>, m?: string) => Promise<void> }) {
  const [info, setInfo] = useState<AppInfo | null>(null);
  useEffect(() => {
    api.appInfo().then(setInfo, () => undefined);
  }, []);
  if (!info) return null;

  return (
    <Section
      title="App"
      hint={
        info.desktop
          ? "Closing the window keeps Myelin in the tray, so the wallpaper and reminders keep working."
          : "You're using Myelin in a browser or on the wallpaper. Install the Myelin app for a window, tray icon, reminders and a hotkey."
      }
    >
      {info.windows && info.autostart !== null && (
        <label className="check-field">
          <input
            type="checkbox"
            checked={info.autostart}
            onChange={async (e) => setInfo({ ...info, autostart: (await api.setAutostart(e.target.checked)).autostart })}
          />
          Start Myelin when I sign in
        </label>
      )}
      <label className="check-field">
        <input type="checkbox" checked={s.notifications} onChange={(e) => save({ notifications: e.target.checked })} />
        Remind me before prayers, when a block starts, and when a focus timer ends
      </label>
      {info.hotkey && (
        <p className="muted small hotkey-note">
          Press <kbd>{info.hotkey}</kbd> anywhere to type "busy till 3" or "note …" without leaving what you're doing.
        </p>
      )}
      <p className="muted small">Myelin {info.version}</p>
    </Section>
  );
}

function LockScreens({ s, save }: { s: SettingsT; save: (p: Partial<SettingsT>, m?: string) => Promise<void> }) {
  const [st, setSt] = useState<LockScreenStatus | null>(null);
  const [stamp, setStamp] = useState(Date.now());
  const [copied, setCopied] = useState(false);
  const load = () => api.lockscreen().then(setSt, () => undefined);
  useEffect(() => {
    load();
  }, [s.phone_access, s.windows_lockscreen, s.phone_key]);

  const copy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      /* select-and-copy still works */
    }
  };

  const fmt = new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" });
  return (
    <Section
      title="Lock screens"
      hint="Windows and iPhone don't allow live widgets on the lock screen, but both show a picture. Myelin draws one of your day and keeps it current."
    >
      <div className="lock-previews" aria-hidden="true">
        <img src={`/lockscreen/desktop.png?w=960&h=540&t=${stamp}`} alt="" className="lock-desktop" />
        <img src={`/lockscreen/phone.png?w=393&h=852&t=${stamp}`} alt="" className="lock-phone" />
      </div>
      <button type="button" className="btn quiet small" onClick={() => setStamp(Date.now())}>
        Refresh previews
      </button>

      <h3 className="sub-heading">Windows</h3>
      {st && !st.windows.available ? (
        <p className="hint">This works when Myelin runs on Windows.</p>
      ) : (
        <>
          <label className="check-field">
            <input
              type="checkbox"
              checked={s.windows_lockscreen}
              onChange={(e) => save({ windows_lockscreen: e.target.checked }, e.target.checked ? "Your lock screen will update within a minute, then every 15 minutes." : "Saved.")}
            />
            Keep my Windows lock screen up to date
          </label>
          {st?.windows.last_set && (
            <p className="muted small">Last updated at {fmt.format(new Date(st.windows.last_set))}.</p>
          )}
          {st?.windows.error && (
            <p className="form-error">
              Windows said: {st.windows.error}. In Windows Settings, set Personalization, Lock screen to Picture, then try
              again.
            </p>
          )}
          {s.windows_lockscreen && (
            <button type="button" className="btn small" onClick={async () => (await api.refreshWindowsLock(), window.setTimeout(load, 4000))}>
              Update now
            </button>
          )}
        </>
      )}

      <h3 className="sub-heading">iPhone</h3>
      <label className="check-field">
        <input
          type="checkbox"
          checked={s.phone_access}
          onChange={(e) => save({ phone_access: e.target.checked })}
        />
        Let my phone fetch the lock-screen picture on home Wi-Fi
      </label>
      {s.phone_access && st && (
        <>
          {!st.phone.listening_on_network && (
            <p className="form-error">Restart Myelin so your phone can reach it (quit from the tray icon, then open it again).</p>
          )}
          {st.phone.url && (
            <div className="phone-link">
              <code>{st.phone.url}</code>
              <div className="form-actions">
                <button type="button" className="btn small" onClick={() => copy(st.phone.url!)}>
                  {copied ? "Copied" : "Copy link"}
                </button>
                <button type="button" className="btn quiet small" onClick={async () => (await api.newPhoneKey(), load())}>
                  Make a new link
                </button>
              </div>
              <p className="muted small">Only this picture is reachable from your network, and only with this link.</p>
            </div>
          )}
          <ol className="steps">
            <li>On your iPhone, open Shortcuts, then Automation, then New Automation.</li>
            <li>Choose Time of Day, pick a time such as 6:30 a.m., set it to Daily and Run Immediately.</li>
            <li>Add the action Get Contents of URL and paste the link above.</li>
            <li>Add the action Set Wallpaper, choose Lock Screen, and turn off Show Preview.</li>
            <li>Make two more automations, say 12:30 p.m. and 5:30 p.m., so the picture stays fresh.</li>
          </ol>
          <p className="muted small">Your phone needs to be on the same Wi-Fi as this computer when the automation runs.</p>
        </>
      )}
    </Section>
  );
}
