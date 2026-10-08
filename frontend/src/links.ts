/**
 * Open a web link in the default browser. Inside Lively or the app window a normal link would
 * navigate the wallpaper itself, so Myelin opens it on the host instead.
 */
export async function openLink(url: string): Promise<void> {
  try {
    const res = await fetch("/api/open", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    if (res.ok) return;
  } catch {
    /* fall back below */
  }
  window.open(url, "_blank", "noopener");
}
