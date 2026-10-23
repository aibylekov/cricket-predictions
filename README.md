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
- ✅ 3.1 Confidence & framing (вероятност → лента увереност + рамка тон).
- ✅ 3.2 Prediction payload schema (само числа, без проза).
- ✅ 3.3 Content generator (итерация 2 — виж статуса по-долу).
- ⬜ 3.4 Human review + publish (следващо: home-grounds review ingest).
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

- ✅ Фаза 2: validation harness (walk-forward, PASS self-test) + baselines
    + logistic v1/v2.
    · Модел v2 (C=0.01): НАЙ-ДОБЪР оценител на вероятности (log_loss 0.6849
      / brier 0.2457, бие form_favourite 0.6888 / 0.2473). Accuracy 55.0%
      срещу 57.3% на летвата — приет компромис (calibration-first за
      confidence framing).
    · Калибрация: средните кофи почти точни (60-70% → 63.9% реално).
      Дефект: 20-40% диапазонът песимистичен (малки n).
    · IPL: непобеден от нищо; калибрацията там ОБЪРНАТА (анти-сигнал);
      моделът сам научи да дисконтира IPL home етикета (−0.047).
      ИЗВОД: следващата IPL печалба е ДАННИ (playing XI / availability =
      Level 1 фундаментален слой), не моделиране.
    · Линеен таван достигнат — league/gap фичъри добавиха ~нищо след
      регуляризацията.

**Пренесени задачи (записани в L3 manifest):**
- TEAM-LEVEL ODDS BRIDGE: подравняване на odds home/away с нашия home_team
  (61-те priced мача; ориентацията още непотвърдена).
- Известни приети ограничения: day_night timezone евристика; is_neutral_venue
  хваща само международни неутрални венюта.

- ✅ ФАЗА 3: CONTENT GENERATOR — ИТЕРАЦИЯ 2 ЗАВЪРШЕНА (player/standings/
    context enrichment, dual toss modes, home-ground деривация, house
    style mechanically enforced).
    · Генерация: OpenAI API (gpt-4o, temperature 0.7 — стилът иска
      вариация в ритъма), промптът е version-controlled
      (src/content/prompt_template.py) с три разделени роли: FACTS (само
      от payload) / STRUCTURE (TopBookies guide) / STYLE (human-writing
      ruleset + къщни правила + къщен глас от style_profile.md,
      калибриран от docs/voice samples/ 01–04).
    · Payload enrichment (L2, point-in-time, leakage-проверено):
      player_form (top 3 batters/bowlers на отбор; източник: L0 score
      таблици през cricket__players roster join — НЕ ball-by-ball
      comment parse), standings (ДЕРИВИРАНИ от dim_match; суровата
      cricket__tournament_points е current-state-only), match_context
      (номер на мач в турнира, номер на среща в серията, last5 резултати
      с опоненти и маржове), current_event прозорец в team_form,
      home_ground деривация (>=10 мача И >=30% дял на venue =
      HIGH-confidence gate за "home advantage" в прозата).
    · Toss lifecycle: pre_toss (toss-ът МЕХАНИЧНО премахнат от payload-а
      + „ако X спечели тоса / ако Y" сценарии) | post_toss.
    · Механични проверки при генерация (retry loop, max 2 поправки):
      номера само от payload (+ производни win counts), нула em dashes,
      целият Part E banned списък, къщни термини (вкл. "net run rate",
      "our model"), win-проценти само с брой мачове в изречението, без
      3+ десетични знака.
    · Leakage: 8/8 проверки PASS (пълен max_source_date одит + 250
      независими преизчисления на dataset).
    · docs/home-grounds-review.csv (813 реда: 127 high / 212 medium):
      чака редакторски human_decision; при връщане decision-ът става
      авторитетен (override на деривацията, bridge_entity-стил).

- ✅ ИТЕРАЦИЯ 3 (56-коментарното ревю + venues резолюция):
    · VENUES АВТОРИТЕТ: docs/Franchise_Cricket_Venues.xlsx ингестиран
      (src/data/ingest_venue_authority.py -> data/lake/l2/venue_authority/,
      bridge_entity-стил, 12/12 venue имена резолвнати към dim_venue).
      Shared-venue лиги (PSL, LPL, MLC, BPL): ВСИЧКИ home-ground деривации
      отхвърлени; никаква home-advantage проза; изброените венюта = само
      fixture контекст. Sheet1 с празни human_decision -> high-confidence
      gate остава (IPL/BBL/CPL стоят като derived). Leakage suite добави
      venue_authority консистентност: 144 shared-league реда с "изстреляла"
      деривация -> всичките override-нати, 0 home-ground претенции.
    · STAGE LABELS: няма отделно поле в източника; stage живее в
      dim_match.sub_title (Final/Qualifier 1-2/Eliminator/Semi Final/
      Quarter Final/Play-off/Knockout/Challenger/Super 8|Six|Four ->
      group). Парсва се в payload: match_context.stage/stage_label/
      is_knockout + stage на всеки last5_results запис. Knockout мачове:
      промптът задължава "как стигнаха дотук" (кой qualifier/eliminator,
      опонент, марж, venue); точковата таблица = минорен контекст.
    · EVENT+FORMAT LABELS: всеки last5_results запис носи event, format,
      venue. Промпт: никакво смесване на win counts през различни събития
      без етикет; series/tour претенции = само tour-scoped числа (C5
      фиксът); key points и preview се съгласуват по scope.
    · FORMAT НАВСЯКЪДЕ: механична проверка - form-claim изречение без
      T20 токен = violation.
    · PLAYER PHASE SPLITS: нов L2 dataset player_phase (ball-by-ball,
      batter_id/bowler_id = roster keys 1:1; point-in-time, max_source_
      date одит + ball-level recount в leakage теста). Батъри: runs/SR
      по powerplay/middle/death; боулъри: overs разпределение + phase
      economy. В players блока по избраната window; мълчаливо пропуснат
      без ball покритие (~55% от мачовете имат).
    · ПРОМПТ/СТИЛ (механично проверени): fact-repetition cap (стат факт
      максимум 2 пъти, никога verbatim: dup-sentence + 3x-stat check);
      нула мета-prediction изречения (стат-базиран verdict с конкретни
      числа + ясен победител по band); банове prolific/notable/marginal
      + ", the 32nd match of" апозитиви; toss сценарии при еднакъв избор
      -> едно изречение ("whoever wins the toss..."); задължителен
      conditional angle при moderate/close_call ("if X misfire, tilts to
      Y", механично проверен); липсващи данни НИКОГА не се споменават
      (мълчание, не обяснение; regex guard).
    · Leakage: 10/10 проверки PASS. 6-те демо drafts: numbers PASS +
      style PASS (retry loop работи; 1 draft мина на втора генерация).

- ✅ ИТЕРАЦИЯ 4 (38-коментарното v3 ревю — SCOPE & ATTRIBUTION: всяка
    претенция е механично вързана към истинския ѝ обхват):
    · SCOPE-ATTRIBUTION VALIDATOR (C10 root-cause): изречение със scope
      фраза ("this series / the current tour / this event") + win/loss
      брой трябва да ползва tour-scoped числата (current_event /
      standings / last5 записите от текущото събитие); обратното също —
      cross-competition брой без "across competitions" или име на друго
      събитие = violation. Плюс WIN-PAIR проверка: всяко "won/lost N of
      M" се валидира като ДВОЙКА срещу конкретен payload прозорец
      ("won 3 of their last 5" при 4 победи гърми, макар 3 и 5 да
      съществуват поотделно в payload-а).
    · TOSS IMPACT AS DATA (C12 root-cause): детерминистично поле
      conditions.toss_impact (прагове, документирани в payload.py:
      gap=|batfirst−chase|; high при gap≥0.20 или dew∧gap≥0.10;
      moderate при dew или gap≥0.10; иначе low). Toss секцията изразява
      ТОЧНО това ниво; "significant/decisive" механично позволени само
      при high; жаргонът ("toss impact", "rated low") е house-banned.
    · LEAGUE vs FORMAT: match.competition_type (от dim_team.is_national)
      + form_label ("IPL"/"MLC" акроним или име на лигата); франчайз
      мачове етикетират форма с лигата, никога излишно "T20";
      интернационалните пазят T20; venue претенции винаги "T20s"
      (пробата е крос-лигова).
    · VENUE SAMPLE SCOPE: venue_stats.sample_format/first/last (point-
      in-time; нов leakage тест payload_venue_sample — 11/11 PASS);
      Pitch секцията казва пробата ("across the 17 T20s here since June
      2025"); venue win claims дават count И total ("won 10 of the 17",
      C36).
    · REPETITION (затегнато): отличителен стат максимум веднъж в Three
      Key Points + веднъж другаде, никога в 3+ секции (по секции,
      механично).
    · FINALS FRAMING: stage=final → verdict само в title-winning език
      (title/trophy/champions задължителни в затварящата секция), без
      "next stage / advance / qualify for"; при всеки knockout всяко
      "N points" носи "in the group stage" в същото изречение.
    · PRE_TOSS плътност = post_toss (само toss съдържанието се мени);
      банове impeccable/erratic; препратки към други събития се датират
      ("in the World Cup in June 2026" — last5 записите носят date);
      conditional angle може да добави batting-depth клауза.
    · 6-те демо drafts: numbers PASS + style PASS; retry loop-ът върши
      работа (всеки draft мина след 1–2 поправки; 3 drafts регенерирани
      след затягането на win-pair/жаргон проверките).
      Bundle: docs/demo_drafts_review_v4.md.

- 🟨 ИТЕРАЦИЯ 5 (AUTHOR STYLE ROTATION — един къщен глас → 8 ротиращи
    авторски гласа срещу повторяемостта между статиите; чака редакторски
    преглед на demo drafts преди commit):
    · ПРОФИЛИ: docs/author-styles/author-01..08-*.md (изчистени реални
      статии по автор) → src/content/calibrate_author.py (Style
      Calibration анализ, ruleset Part 4 — същият като за къщния профил)
      → src/content/author_profiles/author-NN.md (version-controlled).
      Профилът е САМО глас: ритъм, дължина на изреченията, отварящи/
      затварящи конструкции, регистър, похвати, десет проверими правила.
      Механично измерени входове (разпределение на дължините, дял на
      кратки/дълги изречения, размер на абзаците, класове на отварянията,
      контракции, въпроси) — моделът пише профила върху тези цифри, не
      на око. LEAK CHECK (механичен): нито един отбор/играч/двусловно
      собствено име/статистика от източника не влиза в профила (един
      repair round; иначе файлът се маркира FAILED и скриптът гърми).
      Секция 7 „Conflicts with house rules": механично преброените
      навици на автора, които къщните правила override-ват (em dashes,
      banned words, hedges, липса на контракции, XI/weather блокове).
    · LAYERING RULE (критично): профилът е СЛОЙ ВЪРХУ къщните правила,
      никога замяна. prompt_template.build_system_prompt(author_id) пълни
      единствения VOICE слот на system prompt-а (къщен глас при None);
      всичко останало — FACTS wall, STRUCTURE, sentence mechanics, всички
      banned списъци, self-check — е байт-идентично при всеки автор
      (тест). Всички механични проверки в generate_article.py са
      author-independent (validate_* не приемат автор). Конфликт между
      авторски навик и механично правило → правилото печели.
    · РОТАЦИЯ (no-repeat shuffle): src/content/author_rotation.py —
      разбъркано тесте от 8-те профила, по един на мач в реда на
      генериране за деня, преразбъркване САМО при изчерпване (+ boundary
      guard: първата карта на новото тесте ≠ последната раздадена).
      Мачове от един ден никога не споделят стил, освен ако са >8.
      PERSISTENCE: data/state/author_assignments.json (gitignored state,
      като track record) пази автора по match_id → retry-ове и двойката
      pre_toss/post_toss на един мач винаги получават същия профил.
      Draft header-ът щампова author=author-NN.
    · Тестове: tests/test_author_rotation.py (профили пълни + leak-free,
      layering байт-идентичност, тесте без повторение през 40 seed-а,
      persistence през инстанции/режими, generator wiring с fake client).
      Demo: python -m src.content.generate_article [--modes both]
      [--reset-authors] — трите demo мача като ЕДИН мачов ден.
    · Калибрацията минава през 2 LLM repair round-а + ДЕТЕРМИНИСТИЧНИ
      last-resort стъпки (gpt-4o заменя banned дума с друга banned дума и
      пише „no contractions" като правило въпреки инструкцията): scrub на
      описателния banned речник в секции 1–6 (синоними, никога секция 7),
      drop на anti-house правила от TEN RULES в секция 7, strip на
      примери с измислени цифри. Резултат: 8/8 профила LEAK CHECK PASSED.
    · DEMO (един мачов ден, fresh deck, post_toss): 8731 England v India →
      author-08 (Shoaib Z.); 8250 Washington v MI New York → author-04
      (Vishnu Reddy); 8032 RCB v Gujarat → author-07 (Manish K.). Три
      различни профила; останали в тестето 5.
    · Bundle: docs/demo_drafts_review_v5.md (drafts + reports + трите
      използвани профила) чрез src/content/export_review_bundle.py 5.

- ✅ SCOPE WIDENING: T20 МЪЖЕ + ЖЕНИ (цел: WBBL 2026) + SPRING CHALLENGE 2026
    INGEST (23.10.2026; leakage 11/11 PASS; merge + entity-watch репортите
    прегледани и решенията приложени — виж docs/ingest/):
    · INGEST WORKFLOW: per-table SQL дъмпове от сайта (phpMyAdmin, CREATE/ALTER/
      INSERT под alias имена m/bat/p...) НИКОГА не се source-ват директно в
      cricket_raw. src/data/merge_staging_dump.py: инспекция (DROP/TRUNCATE =
      abort) -> staging db cricket_sc -> id-overlap репорт (identical / changed
      / new) -> вмъкване само на нови редове; changed редове не се презаписват
      (L0 immutable). land_l0 --force --tables <списък> пре-ланда само
      засегнатите таблици. Spring Challenge 2026 (tournament 1906, 21 мача):
      1,732 нови реда, 0 конфликти; cricket__tournaments ред за 1906 ЛИПСВА
      (league_key NULL за 2026 до доставка на дъмпа).
    · L1 SCOPE: format='t20' AND gender IN ('male','female') (build_l1
      --genders). gender е колона в dim_match -> L2 -> L3 -> payload
      (match.gender, sample_format "T20 men"/"T20 women"). venue_stats е
      gender-scoped (venue_key, gender, as_of_date): мъжките venue числа са
      непроменени. Payload тренира само same-gender. validation.load_completed има
      default gender='male' -> training/backtest данните НЕ се променят до
      следващата задача (retrain мъже+жени, league-aware, WBBL отделно).
    · DEDUPE ФИКС (разкрит от женския scope): източникът ползва едно и
      също име за мъжки и женски клуб без "Women" (CPL Barbados Royals/TKR/
      Guyana, Northern Brave, ACT). Колапсът е exact name В РАМКИТЕ на
      gender-а на мачовете; dim_team.team_gender; entity_watch 1d = механична
      охрана (17 remaps, 0 cross-gender). bridge_entity решава двусмислени
      имена през same-date fixture pair (144 линка); CPL double-header
      (odds 550) падна в review вместо тих линк.
    · ENTITY WATCH: src/data/entity_watch.py (bridge-style, преди commit):
      186 нови отбора, 68 нови venue, 117 нови турнира; WBBL 2023/24/25 =
      един league_key, Spring Challenge 2024/25 = един. РЕШЕНИЯ (23.10.2026):
      ACT 353 "Australian Capital Territory" (2024) -> 738 "ACT Meteors Women"
      (2025/26) = одобрен cross-season alias (build_l1 APPROVED_TEAM_ALIASES,
      механична проверка за еднакъв gender, evidence в L1 manifest); Junction
      Oval x3 и Albert Park Suva x2 = MANUAL_MERGES в revise_l1 (мъжкият
      "Junction Oval" ключ, city=Melbourne, остава flag-нат); odds 550 (CPL
      double-header) = REJECTED_ODDS_LINKS в build_bridge (никога линк, никога
      review). Пълен репорт: docs/ingest/scope_widening_report.md.
    · Данни: мъже 4,748 мача (4,601 completed) / жени 1,424 (1,406); WBBL
      59/43/43 мача по сезон; женски ball-by-ball 408/1,424 (phase фичъри
      NULL там); SC 2026: 16/21 мача с player scores (10078-10081 + 10084 без).

🟨 СЛЕДВА (заключено, 23.10.2026): (1) cricket__tournaments дъмп ->
data/raw/spring_challenge_2026/, merge през staging, rebuild L1 за league_key
на SC 2026 (НЕ се измисля league_key дотогава); (2) retrain мъже+жени,
league-aware, WBBL точност отделно.

🟨 Следва (по избор): (а) Level 1 фундаментален слой (Roanuz lineup
endpoint + availability фичъри) — атакува IPL директно; (б) нелинеен
модел (GBM) на същите фичъри; (в) Фаза 3.4 — human review + publish +
home-grounds review ingest.

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
