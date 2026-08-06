# Cricket Predictions — README (жив договор)

> **Този файл е договорът между сесиите.** Claude Code го чете ПРЪВ при всяка задача.
> Съдържа заключените решения, фазовия план със статус и конвенциите. Ако задача
> противоречи на този файл — печели файлът, освен ако изрично го променим в chat.

---

## 0. Какво е това

Полу-автоматизирана система, която генерира betting prediction статии за TheTopBookies.

- **Обхват v1:** само **T20 мъже**. Другите формати/лиги — следващ етап.
- **Източници:** Roanuz (ball-by-ball, платено), odds feed (1x2bet *или* Parimatch — едно стига), вътрешно venue API, weather данни. Историческо raw DB (~600 MB) вече съществува локално.
- **Инструменти:** Claude chat (архитектура) → Cowork (скеле) → Claude Code (код) → GitHub Actions (автоматично изпълнение). Разработка **изцяло локално**; Actions влиза чак във Фаза 4.

### Двата слоя (фундаментът на всичко)

1. **Prediction engine** — количественият слой. Данни → модел → **числа** (вероятност за победа, score range, toss, props).
2. **Content layer** — Claude пълни guide-шаблона от структуриран „prediction payload" и **само облича числата в проза**.

> **LLM-ът никога не измисля статистика.** Всяко число в статията идва от payload-а. Това е най-важната защита срещу drift на точността.

---

## 1. Основни принципи (не подлежат на предоговаряне)

1. **Строго разделение на слоевете.** Engine смята; content облича. Никога не се смесват.
2. **L0 е immutable.** Raw ball-by-ball не се пипа и не се презаписва. Всичко надолу се смята ОТ него.
3. **Point-in-time коректност.** Всеки агрегат в L2 носи `as_of_date` и се смята само от данни строго преди тази дата. Нула leakage.
4. **Всеки join минава през `bridge_entity`.** Roanuz / odds имена се различават — никога join по име директно.
5. **Прогноза за ВСЕКИ мач.** Увереността мени **тона и фокуса** на статията (confidence & **framing**), а не дали да публикуваме (без gating).
6. **Точност:** 67% е стремеж, не праг. Реалистично при пълно покритие в T20 = високи 50-те до ниски 60-те, растящо с модела. Отчита се на нива (обща + high-confidence).

---

### Фундаментален слой (план)

Фундаменталните данни (обявен състав, контузии, ротация, важност на мача)
влизат ДИСЦИПЛИНИРАНО и заградено. LLM може да ЧЕТЕ/ИЗВЛИЧА, но НИКОГА не
движи вероятности сам.
- **Ниво 1 — structured availability (в модела):** обявеният XI преизчислява
  отборните агрегати за мача (липсващ ключов играч → изключен). Live feed
  от Roanuz, не от историческата база. Backtest-ваемо.
- **Ниво 2 — news signals като тесни структурирани флагове (v2, НЕ MVP):**
  напр. `key_player_doubtful` (0/1), `resting_regulars` (0/1). LLM извлича
  флага от текст; МОДЕЛЪТ учи тежестта от историята. Изисква news ingest +
  внимателен backtest. Отложено до работещ baseline.
- **Ниво 3 — news контекст в ПРОЗАТА (content слой, Фаза 3):** storylines,
  завръщащи се играчи, форма на терен — вплетени в текста, без да пипат
  числата. Безопасно и полезно рано.

Нов вход „Context & news" се разклонява: тънка структурирана част към
модела (Нива 1–2), богата текстова част към content генератора (Ниво 3).

---

## 2. Разделение на инструментите

| Инструмент | Роля |
|---|---|
| **Claude chat** | Решения, архитектура, планиране, промптове. Не пише продукционен код. |
| **Claude Cowork** | Скеле: структура на папките, venv, `requirements.txt`, `.gitignore`, `.env.example`, `README`. |
| **Claude Code** | Същинско програмиране, локално тестване, Git/GitHub, файлът за Actions. |
| **GitHub Actions** | Изпълнява готовия конвейер по разписание — без локалната машина. Само Фаза 4. |

**Правило:** архитектурата се заключва в chat ПРЕДИ да започне код. Предотвратява scope creep.

---

## 3. Машина и файлова конвенция

Машина: **Windows** · терминал: **PowerShell** · потребителска директория: `C:\Users\Corsair`.
Проектът живее като отделна папка: **`C:\Users\Corsair\cricket-predictions`**.

### Критично: папката се създава РЪЧНО преди Cowork

Никога не се оставя инструмент сам да реши къде живее проектът (в миналото това доведе до миграция от временна папка).

```powershell
# 1. Python (на Windows е "python" или "py", НЕ "python3")
python --version
pip --version

# 2. Създай папката ръчно и влез в нея
cd C:\Users\Corsair
mkdir cricket-predictions
cd cricket-predictions

# 3. Виртуална среда
python -m venv venv
.\venv\Scripts\Activate.ps1      # в началото на реда трябва да се появи (venv)

# 4. Зависимости (след като Cowork е създал requirements.txt)
pip install -r requirements.txt
```

Ако активирането е блокирано („running scripts is disabled"):
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force
```
Резервно, ако venv откаже изобщо — Python на средата директно:
```powershell
.\venv\Scripts\python.exe -m src.pipeline
```

---

## 4. Целева структура на проекта

```
cricket-predictions/
├─ README.md            ← ТОЗИ файл (жив договор: фазен план + статус)
├─ .gitignore           ← слага се ПРЕДИ първия commit
├─ .env.example         ← шаблон; истинският .env НИКОГА в Git
├─ requirements.txt
├─ src/
│  ├─ ingest/           ← roanuz / odds / weather адаптери
│  ├─ data/             ← L0→L1→L2→L3 трансформации (DuckDB)
│  ├─ features/         ← сглобяване на L3 feature row
│  ├─ model/
│  │  ├─ train.py       ← ТЕЖЪК, локален: пипа 600MB, преобучава
│  │  ├─ backtest.py    ← ТЕЖЪК, локален: walk-forward валидация
│  │  └─ predict.py     ← ЛЕК: зарежда трениран модел, 1 мач
│  ├─ content/          ← payload schema + генератор по guide-а
│  ├─ publish.py
│  └─ pipeline.py       ← ЕДНО предсказание end-to-end (леко, CI-friendly)
├─ data/
│  ├─ raw/              ← 600MB immutable DB (gitignored, САМО локално)
│  ├─ derived/          ← L2/L3 parquet (gitignored)
│  └─ track_record.db   ← състояние (gitignored; cache/artifact в CI)
├─ models/              ← трениран артефакт (малък, може в Git)
├─ logs/
├─ tests/
├─ legacy/              ← стари скриптове, само за справка
└─ .github/workflows/
   └─ predict.yml       ← разписание за Actions (Фаза 4)
```

---

## 5. Разделението train / predict (най-важната адаптация от предишния проект)

Предишният проект се счупи, защото база расте през commit-back и repo-то набъбна (>100 MB).
Тук стартираме от 600 MB — затова правим структурно разделение, което гарантира, че **нищо голямо никога не влиза в GitHub**:

| | Кога | Какво пипа | Къде |
|---|---|---|---|
| **train.py / backtest.py** | рядко, ръчно | 600MB raw DB | само локално |
| **pipeline.py (predict)** | на всяко пускане | малкия трениран модел (~MB) + данни само за 1 предстоящ мач | локално и в CI |
| **track_record** | всяко пускане | малък state | cache/artifact или малък external Postgres — НИКОГА commit-back |

> **Git не е база данни.** 600-те MB, derived parquet, track record — всичко променящо се минава през gitignore + external storage/cache, никога през commit.

---

## 6. Модел на данните (L0–L3)

Целевата схема е разписана с работещ пример в **`TopBookies_Data_Model_Worked_Example.xlsx`** (един sheet на таблица, проследим фиктивен мач `M2026_0412` през всички слоеве, жива de-vig сметка). Тя е спецификацията за Фаза 1.

Накратко: **L0** raw ball-by-ball (immutable) → **L1** dims + `bridge_entity` → **L2** агрегати с `as_of_date` → **L3** плосък feature row (един ред = един мач; единственото, което моделът чете).

---

## 7. Тайни · Git · .gitignore

**Модел за тайните (двупистов):** `.env` локално (в `.gitignore`) · **GitHub → Settings → Secrets and variables → Actions** в продукция. Никога в кода, никога в commit. При съмнение за изтекъл ключ — анулира се и се подменя. Ключът се поставя без интервали/нови редове/невидими символи.

**`.gitignore` — слага се преди първия commit:**
```gitignore
venv/
.venv/
.env
__pycache__/
*.pyc
*.pyo
*.db
*.sqlite
*.sqlite3
data/raw/
data/derived/
Thumbs.db
.DS_Store
.vscode/
.idea/
```

**Първо качване (Public repo, акаунт `aibylekov`, име = `cricket-predictions`):**
```powershell
cd C:\Users\Corsair\cricket-predictions
git init
git add .
git status          # ПРОВЕРКА: само код и документация. Ако видиш venv/ или .env — СПРИ.
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/aibylekov/cricket-predictions.git
git push -u origin main
```
Автентикация: HTTPS през Git Credential Manager (браузър при първо качване). Без SSH/CLI.

---

## 8. GitHub Actions (Фаза 4)

- **Тригери:** `workflow_dispatch` (ръчно — тества се ПРЕДИ да се разчита на cron) + `schedule`.
- **Тайминг на toss — крикет-специфичен капан.** Actions не гарантира точна минута (бави се 5–15 мин под натоварване). Затова: **preview статия** (T-2 дни / сутрин) по cron; **toss-заключена финална версия** по събитие/ръчно, не по точен час.
- **Крикетът е предимство:** мачовете са насрочени събития, не поток — няма нужда от агресивен cron на 15 мин, значи Actions е по-спокоен.
- **Състояние:** track record през **cache/artifact**, възстановяван в началото и записван в края. Никога commit-back.
- **Аларма при провал** + идемпотентни маркери (без дублирано публикуване).

---

## 9. Фазен план + СТАТУС (build sequence)

Ръководен принцип: **walking skeleton** — една прогноза от край до край възможно най-рано (дори с „тъп" модел = самите odds), после удебеляваме всяка част. Всеки компонент е тестваем сам за себе си.

**Легенда:** ⬜ предстои · 🟨 в ход · ✅ готово

### Фаза 0 — Скеле (локално)
- ⬜ Ръчно създадена папка → Cowork изгражда структурата, venv, requirements, .gitignore, .env.example.
- **Готово, когато:** тривиален pipeline прекарва един файл end-to-end.

### Фаза 1 — Гръбнак на данните = структуриране на raw DB (локално)
- ⬜ 1.1 Профилиране на 600MB DB (таблици, grain, покритие по дати, null rate, дупки).
- ⬜ 1.2 L0 landing като immutable Parquet, партициониран по сезон/турнир, read-only.
- ⬜ 1.3 L1 dims + `bridge_entity` (entity resolution Roanuz ↔ odds ↔ internal).
  **1.3 L1 dims + bridge_entity — includes these locked fixes:**
    - Recover the 1970-01-01 date: 82 rows in `over_summary_balls.updated`;
      rebuild via `over_summary_id → over_summaries.match_id →
      cricket__matches.start_at`. `entry_time` is clean; use it as primary.
    - Parse batter/bowler out of `over_summary_balls.comment` text
      (format e.g. "Bowler to Batter: outcome."). Populate proper
      `batter_id` / `bowler_id` columns in L1.
    - **LEAKAGE RULE:** `cricket__players.playing_xi` is filled only AFTER a
      match is played. It is allowed ONLY as a historical feature for
      past matches. It MUST NOT be used as a pre-match feature for
      upcoming predictions (data leakage). For live predictions the
      announced XI comes from the Roanuz lineup endpoint (~30–40 min
      before toss), never from this DB.
- ⬜ 1.4 L2 агрегати с `as_of_date`.
- ⬜ 1.5 L3 feature-row assembler.
- **Готово, когато:** L1 → един Roanuz ID и едно odds-име се резолвят към същия `internal_id`; L2 → leakage тест доказва, че агрегат за дата D не ползва ред с дата ≥ D; L3 → feature row за исторически мач се сверява ръчно.

### Фаза 2 — Baseline модел + линийка за мерене (локално)
- ⬜ 2.1 Validation harness ПРЕДИ модела: walk-forward split по време, log loss / Brier / calibration / accuracy.
- ⬜ 2.2 Baseline: първо „винаги фаворитът по devig odds", после прост logistic/GBM на ⭐ фичърите.
- **Готово, когато:** моделът поне настига odds-baseline на backtest.

- **ТУРНИРЕН ПОДХОД (заключено):** Обучаваме на ВСИЧКИ T20 мъже (обем + обща
  механика на формата), НЕ само IPL. Но:
    - `tournament` влиза като характеристика, за да може моделът да различава
      IPL от по-слаби лиги.
    - Точността се МЕРИ и ПУБЛИКУВА с осъзнаване по турнир — отделен % за IPL,
      BBL и т.н., не една обща цифра. IPL е водещият случай.
    - Забележка за odds: историческите odds покриват предимно големите
      турнири (~354 мача общо), затова валидацията срещу пазара е реално
      възможна само там. Малките лиги учат форма, но не се валидират срещу odds.

- **ВАЛИДАЦИЯ — две отделни неща (заключено):**
    - ОСНОВНА валидация на ТОЧНОСТТА: използва ВСИЧКИ завършени T20-мъжки
      мачове (~4,763, is_completed=true), с осъзнаване по турнир (отделен %
      за IPL, BBL и т.н.). Хиляди мачове — извадката е богата. Това е
      метриката, която значи най-много за целта ни (точност + доверие).
    - ВТОРИЧНА проверка СРЕЩУ ПАЗАРА: сравнява модела с odds (log loss /
      Brier / калибрация спрямо devig implied prob). Възможна само за
      мачовете с исторически odds (~60–75 T20-мъжки, тънка извадка).
      Ограничена по обхват; НЕ ограничава основната валидация на точността.
    - Причина за тънките odds: базата пази odds само за малка, скорошна част
      от мачовете; останалите мачове са напълно валидни, просто без записана
      историческа цена. Live feed-ът ще трупа още odds занапред.

### Фаза 3 — Прогноза → статия (скелетът оживява, локално)
- ⬜ 3.1 Confidence & framing (вероятност → лента увереност + рамка тон).
- ⬜ 3.2 Prediction payload schema (само числа, без проза).
- ⬜ 3.3 Content generator (Claude пълни guide-шаблона; не измисля нищо).
- ⬜ 3.4 Human review + publish.
- **Готово, когато:** статията съдържа само числа, налични в payload-а.

### Фаза 4 — Автоматизация (GitHub Actions)
- ⬜ 4.1 Outcome ingest + scoring + track record.
- ⬜ 4.2 `predict.yml` (dispatch → cron), state през cache/artifact, аларма при провал.
- **Готово, когато:** едно ръчно пускане в Actions генерира и публикува прогноза без локалната машина.

**Итерации след това:** score/toss/props модели, matchup фичъри (v2).

### Текущ статус (обновявай тук всяка сесия)
- ✅ DATA СЛОЙ ЗАВЪРШЕН: L0 → L1 → L2 → L3, leakage-проверен, на GitHub.
    · L3 feature-row assembler: една плоска таблица, един ред на мач
      (home_/away_ блокове + venue + conditions + odds + target winner).
    · is_neutral_venue + home_team_source (честен сигнал за надеждността на "home").
    · L3 leakage re-check: PASS. Никакви редове изхвърлени (липси = NULL).
- ✅ Целият data слой (скриптове + тестове) на GitHub; Parquet gitignore-нат.

**Пренесени задачи за Фаза 2 (записани в L3 manifest):**
- TEAM-LEVEL ODDS BRIDGE: подравняване на odds home/away с нашия home_team
  (61-те priced мача; ориентацията още непотвърдена).
- Tournament-aware accuracy reporting (отделен % по league_key, IPL водещ).
- Известни приети ограничения: day_night timezone евристика; is_neutral_venue
  хваща само международни неутрални венюта.

🟨 Следва: Фаза 2 — validation harness ПЪРВО (walk-forward split, log loss /
Brier / calibration / accuracy), после odds-baseline + baseline модел.

---

## 10. Работен цикъл на сесия + шаблони

1. **Chat:** обсъжда какво следва → формулира задача.
2. **Chat → Code/Cowork:** задачата се дава като кратък изричен блок.
3. **Изпълнение:** Code чете `README.md`, имплементира, тества локално, commit + push.
4. **Ти:** ръчно `workflow_dispatch` за потвърждение (когато сме във Фаза 4).
5. **Chat:** резултатът се преглежда, статусът в раздел 9 се обновява.

**Шаблон за Cowork:**
```
Използвай СЪЩЕСТВУВАЩАТА папка C:\Users\Corsair\cricket-predictions.
Не създавай нова директория и не работи във временна папка.
Изгради вътре структурата от README раздел 4, плюс requirements.txt,
.gitignore (раздел 7), .env.example и остави README.md непокътнат.
```

**Шаблон за Claude Code:**
```
Task for Claude Code (point it at C:\Users\Corsair\cricket-predictions):

Read README.md first, then:
1. <конкретна стъпка от текущата фаза>
2. <конкретна стъпка>
3. Secrets are read from .env locally / GitHub Actions Secrets in CI —
   list exactly which ones I need to add and where.
4. Commit + push. Confirm it appears in the repo's Actions tab.
```

---

## 11. Капани (научени на практика + крикет-специфични)

| Капан | Решение |
|---|---|
| Проектът се създава във временна папка | Папката се създава ръчно преди Cowork; Cowork се насочва към нея |
| `git add .` качва `venv` и `.env` | `.gitignore` преди първия commit + задължителен `git status` |
| Repo набъбва и спира проекта | Състояние през Actions cache/artifact, никога commit-back |
| **600MB raw DB попада в Git** | `data/raw/` в `.gitignore`; пипа се само от `train.py`/`backtest.py` локално |
| Дублирани публикувания между run-ове | Идемпотентни маркери + запазено състояние |
| API ключ в Secrets дава HTTP header грешка | Ключ без интервали/нови редове/невидими символи |
| `python3` не работи в PowerShell | На Windows е `python` или `py` |
| Активирането на venv е блокирано | `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force` |
| Cron гърми на празен ход преди тест | `workflow_dispatch` за ръчно пускане първо |
| **Toss-времето се разминава с cron** | Preview по cron; toss-заключена версия по събитие/ръчно, не по точен час |
| **LLM измисля статистика в прозата** | Content слоят чете само от prediction payload; нищо извън него |
