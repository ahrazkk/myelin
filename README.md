# Myelin

Myelin turns your Windows desktop wallpaper into a live daily plan, streak tracker and prayer clock. Every feature is built on what research says actually rewires habits.

Practice wraps nerve pathways in myelin, the insulation that makes signals fire faster. Myelin draws your streak the same way: each day you finish your plan wraps one segment of an axon, across the 66 days habits take on average to become automatic.

![Myelin by day: the clock, the streak drawn as an axon, today's plan and prayer times](docs/wallpaper-day.png)

After Maghrib the wallpaper switches to a night view, styled like a fluorescence microscope:

![Myelin at night, with today's segment wrapped](docs/wallpaper-night.png)

_Screenshots use sample data._

## What it does today (v0.1)

- **Today's plan** from a weekly rotation that interleaves two interview tracks a day (LeetCode Python, LeetCode SQL, system design, resume, a new skill), plus Quran after Fajr and gym on gym days.
- **One master streak**, drawn as an axon across a 66-day cycle. Missed days stay bare instead of turning red.
- **Prayer times** calculated offline with the [Adhan](https://github.com/batoulapps/Adhan) algorithm (ISNA by default, any major method, standard or Hanafi Asr), a countdown to the next prayer, and the Hijri date, which turns over at Maghrib.
- **Day and night views** that switch at Maghrib and sunrise.
- **Local-first:** a small Python server on your PC and one SQLite file. No account, no cloud, and your location never leaves your computer.

## Why it works the way it does

| Finding | How Myelin uses it |
| --- | --- |
| Habits took a median of 66 days to become automatic, and one missed day did not derail them ([Lally et al., 2010](https://jamesclear.com/new-habit)). | A 66-day cycle, and a streak that bends instead of breaking. |
| Interleaving, spacing and retrieval practice are among the best-supported learning strategies ([Weinstein et al., 2018](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5780548/)). | Two different tracks every day, and a spaced re-solve day. |
| A single bout of aerobic exercise primes learning for at least 30 minutes afterward ([study](https://pmc.ncbi.nlm.nih.gov/articles/PMC4857085)). | Gym is placed right before the study blocks. |
| If-then plans have a medium-to-large effect on reaching goals ([Gollwitzer & Sheeran](https://kops.uni-konstanz.de/handle/123456789/69905)). | Every habit has an anchor, like Quran right after Fajr. |

## Set it up on Windows

You need about 10 minutes. The setup script installs Python and Node.js with winget if they're missing.

1. Clone this repo, open PowerShell in the folder, and run:
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
   ```
2. Start Myelin. On first run it opens settings, so you can share your location for prayer times:
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\start.ps1
   ```
3. Make it start whenever you sign in:
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\install-startup.ps1
   ```
4. Install [Lively Wallpaper](https://github.com/rocksdanister/lively) from the Microsoft Store. Choose **Add wallpaper**, enter `http://127.0.0.1:8765/`, and set it as your wallpaper. Turn on mouse input for wallpapers in Lively's settings so you can tick things off right on the desktop.

Lively pauses the wallpaper while a full-screen app runs, so games and video calls aren't affected.

## Change your routine

Your tracks, weekly rotation and gym days live in [`backend/myelin/defaults/routine.json`](backend/myelin/defaults/routine.json). Edit it and restart Myelin; new days use the new routine.

## Develop

```bash
# Server (Python 3.11+)
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
python -m myelin                                    # http://127.0.0.1:8765

# Wallpaper (Node 20+), in a second terminal
cd frontend
npm install
npm run dev                                         # http://localhost:5173, forwards /api to the server
```

| Folder | What's in it |
| --- | --- |
| `backend/myelin` | FastAPI server, SQLite models, planner, streak and prayer-time logic |
| `backend/tests` | pytest suite (planner, prayer times, API and streak rules) |
| `frontend/src` | React + TypeScript wallpaper and settings screens |
| `scripts` | Windows setup, start and sign-in scripts |

## Roadmap

- [x] **Phase 0, setup:** server, database, wallpaper, prayer times, check-offs, streak
- [ ] **Phase 1, core loop:** streak freezes, never-miss-twice, a rescue minimum for busy days, 66-day meters per habit, year heatmap, daily hadith
- [ ] **Phase 2, smart scheduling:** "busy till 3" input that reshuffles the day, Google Calendar and Outlook sync, spaced re-solve queue, automatic logging from NeetCode submissions, phone access on home Wi-Fi
- [ ] **Phase 3, AI and polish:** bring-your-own AI (Claude, OpenAI, Gemini or local Ollama), labeled hadith explanations, quizzes, mock interviews, focus timer
- [ ] **Phase 4, v1.0:** setup wizard, templates and content packs, layout editor, Windows installer

## License

[MIT](LICENSE)
