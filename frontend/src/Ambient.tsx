import { useEffect, useRef } from "react";
import type { BackgroundMode, CursorEffect, Weather, WeatherScene } from "./api";

/*
  The living background behind every tab: the sky outside your window, or drifting neurons, plus an
  optional effect that follows the cursor. It's one canvas under the content, so it never covers text.
  It runs at about 30 frames a second, stops while the window is hidden, and stays still when
  Reduce motion is on.
*/

export interface AmbientProps {
  mode: BackgroundMode;
  weather: Weather | null;
  night: boolean;
  cursor: CursorEffect;
  still: boolean;
  /** Changes whenever theme or accent colours change, so the canvas re-reads them. */
  paletteKey: string;
}

export function Ambient(props: AmbientProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const engineRef = useRef<Engine | null>(null);

  useEffect(() => {
    const engine = new Engine(canvasRef.current!);
    engineRef.current = engine;
    return () => engine.destroy();
  }, []);

  useEffect(() => {
    engineRef.current?.update(props);
  }, [props.mode, props.weather, props.night, props.cursor, props.still, props.paletteKey]);

  return <canvas ref={canvasRef} className="ambient" aria-hidden="true" />;
}

/* ---------------------------------------------------------------- colours */

type RGB = [number, number, number];

function parseColor(value: string, fallback: RGB): RGB {
  const v = value.trim();
  const hex = v.match(/^#([0-9a-f]{6})$/i);
  if (hex) {
    const n = parseInt(hex[1], 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  }
  const rgb = v.match(/rgba?\(\s*(\d+)[ ,]+(\d+)[ ,]+(\d+)/i);
  if (rgb) return [Number(rgb[1]), Number(rgb[2]), Number(rgb[3])];
  return fallback;
}

const rgba = (c: RGB, a: number) => `rgba(${c[0]},${c[1]},${c[2]},${Math.max(0, Math.min(1, a))})`;
const mix = (a: RGB, b: RGB, t: number): RGB => [
  Math.round(a[0] + (b[0] - a[0]) * t),
  Math.round(a[1] + (b[1] - a[1]) * t),
  Math.round(a[2] + (b[2] - a[2]) * t),
];

interface Palette {
  slide: RGB;
  ink: RGB;
  accent: RGB;
  cresyl: RGB;
}

function readPalette(): Palette {
  const s = getComputedStyle(document.documentElement);
  return {
    slide: parseColor(s.getPropertyValue("--slide"), [237, 239, 245]),
    ink: parseColor(s.getPropertyValue("--ink"), [27, 33, 66]),
    accent: parseColor(s.getPropertyValue("--myelin"), [45, 107, 173]),
    cresyl: parseColor(s.getPropertyValue("--cresyl"), [123, 63, 158]),
  };
}

// The top of the sky for each kind of weather. The bottom always fades into the theme's background,
// so text sits on the colour it was designed for.
const SKY_DAY: Record<WeatherScene, RGB> = {
  clear: [196, 218, 243],
  partly: [205, 218, 237],
  cloudy: [209, 214, 224],
  fog: [222, 225, 231],
  drizzle: [203, 211, 222],
  rain: [190, 199, 214],
  snow: [221, 228, 238],
  storm: [174, 184, 201],
};
const SKY_NIGHT: Record<WeatherScene, RGB> = {
  clear: [4, 8, 28],
  partly: [6, 11, 33],
  cloudy: [17, 25, 49],
  fog: [22, 29, 52],
  drizzle: [14, 22, 46],
  rain: [11, 18, 40],
  snow: [20, 28, 54],
  storm: [7, 11, 29],
};

/* ---------------------------------------------------------------- the scene */

interface Star { x: number; y: number; r: number; phase: number; speed: number }
interface Cloud { x: number; y: number; w: number; speed: number; sprite: number }
interface Drop { x: number; y: number; len: number; speed: number }
interface Flake { x: number; y: number; r: number; speed: number; phase: number }
interface Mist { y: number; h: number; x: number; speed: number; alpha: number }
interface Neuron { x: number; y: number; vx: number; vy: number }
interface Pulse { a: number; b: number; born: number; dur: number }
interface Spark { x: number; y: number; vx: number; vy: number; born: number }

const SPARK_LIFE = 1100;
const FRAME_MS = 1000 / 30;

class Engine {
  private ctx: CanvasRenderingContext2D;
  private props: AmbientProps | null = null;
  private W = 0;
  private H = 0;
  private raf = 0;
  private last = 0;
  private palette: Palette = readPalette();

  private stars: Star[] = [];
  private clouds: Cloud[] = [];
  private sprites: HTMLCanvasElement[] = [];
  private drops: Drop[] = [];
  private flakes: Flake[] = [];
  private mist: Mist[] = [];
  private neurons: Neuron[] = [];
  private pulses: Pulse[] = [];
  private sparks: Spark[] = [];
  private nextFlash = 0;
  private flashAt = -1e9;
  private nextPulse = 0;
  private blank = false;

  private pointer = { x: -1e4, y: -1e4, ex: -1e4, ey: -1e4, moved: -1e9, spawnX: -1e4, spawnY: -1e4 };

  constructor(private canvas: HTMLCanvasElement) {
    this.ctx = canvas.getContext("2d")!;
    window.addEventListener("resize", this.onResize);
    window.addEventListener("pointermove", this.onPointer, { passive: true });
    document.addEventListener("pointerleave", this.onLeave);
    document.addEventListener("visibilitychange", this.onVisibility);
    this.resize();
  }

  destroy() {
    cancelAnimationFrame(this.raf);
    window.removeEventListener("resize", this.onResize);
    window.removeEventListener("pointermove", this.onPointer);
    document.removeEventListener("pointerleave", this.onLeave);
    document.removeEventListener("visibilitychange", this.onVisibility);
  }

  update(props: AmbientProps) {
    const prev = this.props;
    this.props = props;
    this.palette = readPalette();
    const sceneChanged =
      !prev ||
      prev.mode !== props.mode ||
      prev.night !== props.night ||
      prev.paletteKey !== props.paletteKey ||
      sceneOf(prev.weather) !== sceneOf(props.weather) ||
      intensityOf(prev.weather) !== intensityOf(props.weather);
    if (sceneChanged) this.build();
    this.schedule();
  }

  private get animating() {
    const p = this.props;
    return !!p && !p.still && (p.mode !== "plain" || p.cursor !== "off");
  }

  private schedule() {
    cancelAnimationFrame(this.raf);
    if (this.animating) {
      this.last = performance.now();
      this.raf = requestAnimationFrame(this.loop);
    } else {
      this.frame(0, performance.now()); // one still frame
    }
  }

  private loop = (now: number) => {
    this.raf = requestAnimationFrame(this.loop);
    if (document.hidden) {
      this.last = now;
      return;
    }
    const dt = now - this.last;
    if (dt < FRAME_MS - 2) return;
    this.last = now;
    this.frame(Math.min(dt, 100) / 1000, now);
  };

  private onResize = () => {
    this.resize();
    this.build();
    if (!this.animating) this.frame(0, performance.now());
  };

  private onPointer = (e: PointerEvent) => {
    const p = this.pointer;
    if (p.x < -1e3) {
      p.ex = e.clientX;
      p.ey = e.clientY;
    }
    p.x = e.clientX;
    p.y = e.clientY;
    p.moved = performance.now();
    if (this.props?.cursor === "synapses" && !this.props.still) {
      const dx = p.x - p.spawnX;
      const dy = p.y - p.spawnY;
      if (dx * dx + dy * dy > 18 * 18) {
        p.spawnX = p.x;
        p.spawnY = p.y;
        this.sparks.push({
          x: p.x,
          y: p.y,
          vx: (Math.random() - 0.5) * 22,
          vy: (Math.random() - 0.5) * 22,
          born: p.moved,
        });
        if (this.sparks.length > 90) this.sparks.shift();
      }
    }
  };

  private onLeave = () => {
    this.pointer.moved = -1e9;
  };

  private onVisibility = () => {
    if (!document.hidden) this.last = performance.now();
  };

  private resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
    this.W = window.innerWidth;
    this.H = window.innerHeight;
    this.canvas.width = Math.round(this.W * dpr);
    this.canvas.height = Math.round(this.H * dpr);
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  /* -------- building the scene */

  private build() {
    const p = this.props;
    if (!p) return;
    const { W, H } = this;
    const area = (W * H) / (1920 * 1080);
    const rand = (a: number, b: number) => a + Math.random() * (b - a);
    const scene = sceneOf(p.weather);
    const intensity = intensityOf(p.weather);

    this.stars = [];
    this.clouds = [];
    this.drops = [];
    this.flakes = [];
    this.mist = [];
    this.neurons = [];
    this.pulses = [];

    if (p.mode === "weather" && scene) {
      const night = p.night;
      if (night && (scene === "clear" || scene === "partly")) {
        const n = Math.round((scene === "clear" ? 150 : 80) * area);
        for (let i = 0; i < n; i++) {
          this.stars.push({ x: rand(0, W), y: rand(0, H * 0.75), r: rand(0.5, 1.5), phase: rand(0, 6.28), speed: rand(0.4, 1.4) });
        }
      }
      const cloudCount: Partial<Record<WeatherScene, number>> = {
        partly: 4, cloudy: 9, drizzle: 6, rain: 7, storm: 8, snow: 6,
      };
      const nClouds = Math.round((cloudCount[scene] ?? 0) * Math.max(0.6, area));
      if (nClouds) {
        const puffy = scene === "partly" || scene === "snow";
        this.sprites = makeCloudSprites(puffy ? "cumulus" : "stratus", cloudTint(scene, night, this.palette));
        for (let i = 0; i < nClouds; i++) {
          const w = (puffy ? rand(0.2, 0.32) : rand(0.38, 0.62)) * W;
          this.clouds.push({
            x: rand(-0.3 * W, W),
            y: puffy ? rand(-0.03 * H, 0.2 * H) : rand(-0.12 * H, 0.34 * H),
            w,
            speed: rand(4, 11) * (1 + windOf(p.weather) / 30),
            sprite: i % this.sprites.length,
          });
        }
      }
      if (scene === "rain" || scene === "drizzle" || scene === "storm") {
        const heavy = scene === "storm" ? 1 : intensity;
        const n = Math.round((scene === "drizzle" ? 70 + 120 * heavy : 90 + 320 * heavy) * area);
        for (let i = 0; i < n; i++) {
          this.drops.push({
            x: rand(-0.1 * W, W),
            y: rand(-H, H),
            len: scene === "drizzle" ? rand(6, 10) : rand(12, 24),
            speed: scene === "drizzle" ? rand(320, 460) : rand(620, 920),
          });
        }
      }
      if (scene === "snow") {
        const n = Math.round((70 + 230 * intensity) * area);
        for (let i = 0; i < n; i++) {
          this.flakes.push({ x: rand(0, W), y: rand(-H, H), r: rand(1, 3.2), speed: rand(18, 52), phase: rand(0, 6.28) });
        }
      }
      if (scene === "fog") {
        for (let i = 0; i < 5; i++) {
          this.mist.push({ y: rand(0.15, 0.95) * H, h: rand(0.12, 0.22) * H, x: rand(0, W), speed: rand(6, 14), alpha: rand(0.18, 0.32) });
        }
      }
      this.nextFlash = performance.now() + rand(4000, 9000);
    }

    if (p.mode === "neural") {
      const n = Math.round(90 * area);
      for (let i = 0; i < n; i++) {
        this.neurons.push({ x: rand(0, W), y: rand(0, H), vx: rand(-7, 7), vy: rand(-7, 7) });
      }
      this.nextPulse = 0;
    }
  }

  /* -------- each frame */

  private frame(dt: number, now: number) {
    const p = this.props;
    if (!p) return;
    const { ctx, W, H } = this;
    // Plain background with the cursor at rest: nothing to draw, so don't spend any effort.
    if (p.mode === "plain" && now - this.pointer.moved > 3000 && this.sparks.length === 0) {
      if (!this.blank) ctx.clearRect(0, 0, W, H);
      this.blank = true;
      return;
    }
    this.blank = false;
    ctx.clearRect(0, 0, W, H);
    const t = now / 1000;
    const moving = !p.still;

    if (p.mode === "weather") this.drawWeather(dt, t, now, moving);
    if (p.mode === "neural") this.drawNeural(dt, now, moving);
    if (moving) this.drawCursor(dt, now);
  }

  private drawWeather(dt: number, t: number, now: number, moving: boolean) {
    const p = this.props!;
    const { ctx, W, H, palette } = this;
    const scene = sceneOf(p.weather) ?? "clear";
    const known = sceneOf(p.weather) !== null;
    const isDay = p.weather && p.weather.available ? p.weather.is_day : !p.night;

    // Sky: the weather's colour at the top, fading into the theme background by two thirds down.
    const top = known ? (p.night ? SKY_NIGHT : SKY_DAY)[scene] : mix(palette.slide, p.night ? [0, 0, 0] : [200, 215, 238], 0.25);
    const g = ctx.createLinearGradient(0, 0, 0, H);
    g.addColorStop(0, rgba(top, 1));
    g.addColorStop(0.68, rgba(mix(top, palette.slide, 0.85), 1));
    g.addColorStop(1, rgba(palette.slide, 1));
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, W, H);
    if (!known) return;

    const cx = W * 0.6;
    const cy = H * 0.12;

    // Sun or moon, kept away from the clock (left) and the tabs (right).
    if (scene === "clear" || scene === "partly") {
      if (!p.night && isDay) {
        const breathe = moving ? 0.04 * Math.sin(t * 0.5) : 0;
        const r = Math.max(W, H) * 0.32;
        const sun = ctx.createRadialGradient(cx, cy, 0, cx, cy, r);
        sun.addColorStop(0, `rgba(255,226,170,${0.55 + breathe})`);
        sun.addColorStop(0.18, `rgba(255,226,170,${0.22 + breathe / 2})`);
        sun.addColorStop(1, "rgba(255,226,170,0)");
        ctx.fillStyle = sun;
        ctx.fillRect(0, 0, W, H);
      } else if (p.night && !isDay) {
        const glow = ctx.createRadialGradient(cx, cy, 0, cx, cy, 140);
        glow.addColorStop(0, "rgba(220,226,250,0.16)");
        glow.addColorStop(1, "rgba(220,226,250,0)");
        ctx.fillStyle = glow;
        ctx.fillRect(cx - 140, cy - 140, 280, 280);
        ctx.fillStyle = "rgba(232,236,248,0.92)";
        ctx.beginPath();
        ctx.arc(cx, cy, 15, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = rgba(top, 0.9); // a crescent: cover part of the disc with sky
        ctx.beginPath();
        ctx.arc(cx + 7, cy - 4, 13, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    for (const s of this.stars) {
      const a = moving ? 0.35 + 0.45 * (0.5 + 0.5 * Math.sin(t * s.speed + s.phase)) : 0.6;
      ctx.fillStyle = `rgba(230,236,255,${a})`;
      ctx.fillRect(s.x, s.y, s.r, s.r);
    }

    for (const c of this.clouds) {
      if (moving) {
        c.x += c.speed * dt;
        if (c.x > W) c.x = -c.w;
      }
      const sprite = this.sprites[c.sprite];
      if (sprite) ctx.drawImage(sprite, c.x, c.y, c.w, (c.w * sprite.height) / sprite.width);
    }

    for (const m of this.mist) {
      if (moving) m.x = (m.x + m.speed * dt) % (W * 1.6);
      const x = m.x - W * 0.3;
      ctx.save();
      ctx.translate(x, m.y);
      ctx.scale(4, 1);
      const r = m.h;
      const fog = ctx.createRadialGradient(0, 0, 0, 0, 0, r);
      const tint = p.night ? [150, 160, 190] : [255, 255, 255];
      fog.addColorStop(0, `rgba(${tint[0]},${tint[1]},${tint[2]},${m.alpha})`);
      fog.addColorStop(1, `rgba(${tint[0]},${tint[1]},${tint[2]},0)`);
      ctx.fillStyle = fog;
      ctx.fillRect(-r, -r, 2 * r, 2 * r);
      ctx.restore();
    }

    if (this.drops.length && moving) {
      const wind = Math.min(0.4, 0.12 + windOf(p.weather) / 120);
      ctx.strokeStyle = p.night ? "rgba(160,186,230,0.32)" : "rgba(64,86,122,0.3)";
      ctx.lineWidth = 1.1;
      ctx.beginPath();
      for (const d of this.drops) {
        d.y += d.speed * dt;
        d.x += d.speed * wind * dt;
        if (d.y > H) {
          d.y = -d.len - Math.random() * 120;
          d.x = Math.random() * W * 1.1 - W * 0.1;
        }
        ctx.moveTo(d.x, d.y);
        ctx.lineTo(d.x - d.len * wind, d.y - d.len);
      }
      ctx.stroke();
    }

    if (this.flakes.length) {
      ctx.fillStyle = p.night ? "rgba(236,240,255,0.85)" : "rgba(132,150,182,0.55)";
      ctx.beginPath();
      for (const f of this.flakes) {
        if (moving) {
          f.y += f.speed * dt;
          f.x += Math.sin(t * 0.8 + f.phase) * 14 * dt;
          if (f.y > H + 4) {
            f.y = -4;
            f.x = Math.random() * W;
          }
        }
        ctx.moveTo(f.x + f.r, f.y);
        ctx.arc(f.x, f.y, f.r, 0, Math.PI * 2);
      }
      ctx.fill();
    }

    // Lightning: a soft, rare glow across the sky, never a hard strobe.
    if (scene === "storm" && moving) {
      if (now > this.nextFlash) {
        this.flashAt = now;
        this.nextFlash = now + 8000 + Math.random() * 9000;
      }
      const e = now - this.flashAt;
      const level = e < 120 ? e / 120 : e < 320 ? 1 - (e - 120) / 200 : e < 420 ? 0.5 * ((e - 320) / 100) : e < 1100 ? 0.5 * (1 - (e - 420) / 680) : 0;
      if (level > 0) {
        ctx.fillStyle = p.night ? `rgba(196,188,255,${0.2 * level})` : `rgba(255,255,255,${0.32 * level})`;
        ctx.fillRect(0, 0, W, H);
      }
    }
  }

  private drawNeural(dt: number, now: number, moving: boolean) {
    const { ctx, W, H, palette } = this;
    const n = this.neurons;
    const reach = 150;
    if (moving) {
      for (const c of n) {
        c.x += c.vx * dt;
        c.y += c.vy * dt;
        if (c.x < -20) c.x = W + 20;
        if (c.x > W + 20) c.x = -20;
        if (c.y < -20) c.y = H + 20;
        if (c.y > H + 20) c.y = -20;
      }
    }

    const links: [number, number, number][] = [];
    ctx.lineWidth = 1;
    for (let i = 0; i < n.length; i++) {
      for (let j = i + 1; j < n.length; j++) {
        const dx = n[i].x - n[j].x;
        const dy = n[i].y - n[j].y;
        const d2 = dx * dx + dy * dy;
        if (d2 < reach * reach) {
          const d = Math.sqrt(d2);
          links.push([i, j, d]);
          ctx.strokeStyle = rgba(palette.accent, (1 - d / reach) * 0.22);
          ctx.beginPath();
          ctx.moveTo(n[i].x, n[i].y);
          ctx.lineTo(n[j].x, n[j].y);
          ctx.stroke();
        }
      }
    }

    ctx.fillStyle = rgba(palette.accent, 0.5);
    ctx.beginPath();
    for (const c of n) {
      ctx.moveTo(c.x + 1.8, c.y);
      ctx.arc(c.x, c.y, 1.8, 0, Math.PI * 2);
    }
    ctx.fill();

    // Signals hop along links now and then, like an impulse jumping node to node.
    if (moving && links.length && now > this.nextPulse) {
      const [a, b] = links[Math.floor(Math.random() * links.length)];
      this.pulses.push({ a, b, born: now, dur: 700 + Math.random() * 500 });
      this.nextPulse = now + 260 + Math.random() * 420;
    }
    this.pulses = this.pulses.filter((q) => now - q.born < q.dur);
    for (const q of this.pulses) {
      const k = (now - q.born) / q.dur;
      const x = n[q.a].x + (n[q.b].x - n[q.a].x) * k;
      const y = n[q.a].y + (n[q.b].y - n[q.a].y) * k;
      const glow = ctx.createRadialGradient(x, y, 0, x, y, 10);
      glow.addColorStop(0, rgba(palette.cresyl, 0.75 * (1 - k * 0.5)));
      glow.addColorStop(1, rgba(palette.cresyl, 0));
      ctx.fillStyle = glow;
      ctx.fillRect(x - 10, y - 10, 20, 20);
    }

    // With the cursor nearby, the closest neurons reach out to it.
    const p = this.pointer;
    const live = now - p.moved < 2500;
    if (moving && live && this.props?.cursor !== "off") {
      for (const c of n) {
        const dx = c.x - p.ex;
        const dy = c.y - p.ey;
        const d = Math.sqrt(dx * dx + dy * dy);
        if (d < 190) {
          ctx.strokeStyle = rgba(palette.accent, (1 - d / 190) * 0.5);
          ctx.beginPath();
          ctx.moveTo(c.x, c.y);
          ctx.lineTo(p.ex, p.ey);
          ctx.stroke();
        }
      }
    }
  }

  private drawCursor(dt: number, now: number) {
    const p = this.props!;
    const { ctx, palette } = this;
    const ptr = this.pointer;
    const ease = 1 - Math.pow(0.0008, dt); // frame-rate independent easing
    ptr.ex += (ptr.x - ptr.ex) * ease;
    ptr.ey += (ptr.y - ptr.ey) * ease;
    const idle = now - ptr.moved;
    const presence = idle < 1500 ? 1 : Math.max(0, 1 - (idle - 1500) / 1200);

    if (p.cursor === "glow" && presence > 0) {
      const r = 260;
      const glow = ctx.createRadialGradient(ptr.ex, ptr.ey, 0, ptr.ex, ptr.ey, r);
      const strength = p.night ? 0.2 : 0.16;
      glow.addColorStop(0, rgba(palette.accent, strength * presence));
      glow.addColorStop(0.35, rgba(palette.accent, strength * 0.45 * presence));
      glow.addColorStop(1, rgba(palette.accent, 0));
      ctx.fillStyle = glow;
      ctx.fillRect(ptr.ex - r, ptr.ey - r, 2 * r, 2 * r);
    }

    if (p.cursor === "synapses") {
      this.sparks = this.sparks.filter((s) => now - s.born < SPARK_LIFE);
      const sp = this.sparks;
      for (const s of sp) {
        s.x += s.vx * dt;
        s.y += s.vy * dt;
      }
      ctx.lineWidth = 1.2;
      for (let i = 0; i < sp.length; i++) {
        const li = 1 - (now - sp[i].born) / SPARK_LIFE;
        for (let j = i + 1; j < sp.length; j++) {
          const dx = sp[i].x - sp[j].x;
          const dy = sp[i].y - sp[j].y;
          const d2 = dx * dx + dy * dy;
          if (d2 > 110 * 110) continue;
          const lj = 1 - (now - sp[j].born) / SPARK_LIFE;
          const a = (1 - Math.sqrt(d2) / 110) * li * lj * (j === i + 1 ? 0.9 : 0.45);
          ctx.strokeStyle = rgba(palette.accent, a);
          ctx.beginPath();
          ctx.moveTo(sp[i].x, sp[i].y);
          ctx.lineTo(sp[j].x, sp[j].y);
          ctx.stroke();
        }
      }
      for (let i = 0; i < sp.length; i++) {
        const life = 1 - (now - sp[i].born) / SPARK_LIFE;
        const newest = i >= sp.length - 3;
        const color = newest ? palette.cresyl : palette.accent;
        const r = 1.6 + 2.2 * life;
        const glow = ctx.createRadialGradient(sp[i].x, sp[i].y, 0, sp[i].x, sp[i].y, r * 4);
        glow.addColorStop(0, rgba(color, 0.65 * life));
        glow.addColorStop(1, rgba(color, 0));
        ctx.fillStyle = glow;
        ctx.fillRect(sp[i].x - r * 4, sp[i].y - r * 4, r * 8, r * 8);
      }
    }
  }
}

/* ---------------------------------------------------------------- helpers */

function sceneOf(w: Weather | null): WeatherScene | null {
  return w && w.available ? w.scene : null;
}

function intensityOf(w: Weather | null): number {
  return w && w.available ? Math.round(w.intensity * 10) / 10 : 0;
}

function windOf(w: Weather | null): number {
  return w && w.available && w.wind_kmh ? w.wind_kmh : 0;
}

interface CloudTint {
  light: RGB; // sunlit top
  shade: RGB; // underside
  alpha: number;
}

function cloudTint(scene: WeatherScene, night: boolean, palette: Palette): CloudTint {
  if (night) {
    const dark = scene === "storm" || scene === "rain";
    return {
      light: mix(dark ? [44, 52, 84] : [64, 74, 112], palette.slide, 0.1),
      shade: dark ? [16, 22, 44] : [28, 36, 64],
      alpha: scene === "partly" ? 0.7 : 0.82,
    };
  }
  if (scene === "partly") return { light: [255, 255, 255], shade: [214, 222, 236], alpha: 0.95 };
  if (scene === "snow") return { light: [250, 251, 254], shade: [206, 213, 226], alpha: 0.9 };
  if (scene === "storm") return { light: [176, 184, 200], shade: [112, 122, 142], alpha: 0.85 };
  if (scene === "rain" || scene === "drizzle") return { light: [214, 220, 230], shade: [150, 160, 178], alpha: 0.82 };
  return { light: [240, 242, 247], shade: [190, 197, 210], alpha: 0.85 }; // overcast
}

/**
 * Cloud shapes, drawn once per scene and reused every frame.
 * Cumulus: a flat base with rounded heaps on top. Stratus: long, layered sheets.
 * Each is lit from above: light on top, shaded underneath.
 */
function makeCloudSprites(kind: "cumulus" | "stratus", tint: CloudTint): HTMLCanvasElement[] {
  const sprites: HTMLCanvasElement[] = [];
  const SW = 720;
  const SH = 300;
  const rnd = (a: number, b: number) => a + Math.random() * (b - a);
  for (let k = 0; k < 3; k++) {
    const c = document.createElement("canvas");
    c.width = SW;
    c.height = SH;
    const g = c.getContext("2d")!;
    g.filter = kind === "cumulus" ? "blur(5px)" : "blur(11px)";
    g.fillStyle = "#fff";
    const shape = new Path2D();
    if (kind === "cumulus") {
      const baseY = 205;
      shape.ellipse(SW / 2, baseY, 245, 42, 0, 0, Math.PI * 2);
      const heaps = 5 + k;
      for (let i = 0; i < heaps; i++) {
        const f = i / (heaps - 1);
        const x = 150 + f * 420 + rnd(-18, 18);
        const r = 48 + 52 * Math.sin(Math.PI * f) + rnd(-8, 12);
        shape.moveTo(x + r, baseY - r * 0.5);
        shape.arc(x, baseY - r * 0.5, r, 0, Math.PI * 2);
      }
    } else {
      const layers = 5 + k;
      for (let i = 0; i < layers; i++) {
        const cx = rnd(170, SW - 170);
        const cy = rnd(120, 190);
        const rx = rnd(110, 190);
        const ry = rnd(26, 46);
        shape.moveTo(cx + rx, cy);
        shape.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
      }
    }
    g.fill(shape);

    // Light from above, shade below, painted only where the cloud is.
    g.filter = "none";
    g.globalCompositeOperation = "source-in";
    const light = g.createLinearGradient(0, 40, 0, 250);
    light.addColorStop(0, rgba(tint.light, tint.alpha));
    light.addColorStop(0.55, rgba(mix(tint.light, tint.shade, 0.35), tint.alpha));
    light.addColorStop(1, rgba(tint.shade, tint.alpha));
    g.fillStyle = light;
    g.fillRect(0, 0, SW, SH);
    sprites.push(c);
  }
  return sprites;
}
