# IT Job Market Observatory

[![CI](https://github.com/us6fu1/it-job-market-observatory/actions/workflows/ci.yml/badge.svg)](https://github.com/us6fu1/it-job-market-observatory/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-dashboard-FF4B4B?logo=streamlit&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)

Это мой пет-проект про рынок вакансий Data Analyst, BI Developer и Data
Engineer. Я сделал его, чтобы потренироваться не на готовом CSV, а на полном
пути данных: запросы к API, RAW, очистка, PostgreSQL, витрины, проверки и
дашборд.

Для живого запуска без токена используется открытый API «Работа России».
Адаптер HeadHunter тоже есть, но для стабильной работы ему нужен OAuth-токен
одобренного приложения.

![Обзор дашборда](docs/images/dashboard-overview.jpg)

## Что уже работает

- загрузка из двух источников в общую модель;
- объединение последних завершённых снимков каждого источника в одной витрине;
- повторные запросы после временных ошибок и HTTP 429/5xx;
- деление больших поисковых сегментов;
- фильтрация нерелевантных названий и удаление дублей;
- обезличенный RAW без email, телефонов и контактных лиц;
- слои `raw`, `stg`, `dwh`, `mart` и `audit` в PostgreSQL;
- снимки вакансий, работодатели, регионы, зарплаты и навыки;
- 39 модульных тестов и 7 SQL-проверок качества;
- CI, который поднимает PostgreSQL 16, прогоняет весь sample-конвейер и
  проверяет запуск дашборда на готовых витринах;
- Streamlit-дашборд с фильтрами по источникам, зарплатной аналитикой,
  журналом загрузок и экспортом выбранного среза в CSV.

## Реальный прогон

Последнюю полную проверку я сделал 26 октября 2026 года. API вернул вакансии,
которые изменялись в течение последних 90 дней.

| Показатель | Результат |
| --- | ---: |
| Проверено строк | 958 |
| Отсеяно по названию | 912 |
| Принято строк | 46 |
| Уникальных вакансий | 36 |
| Работодателей | 22 |
| Регионов | 13 |
| Вакансий с зарплатой | 33 из 36 |
| Ошибок API | 0 |
| Ошибок SQL-проверок | 0 |

Это небольшой срез, поэтому я не выдаю его за полную статистику российского
IT-рынка. Он нужен прежде всего для проверки самого конвейера. Период API
ограничивает дату изменения записи, а дата первой публикации может быть старше.

Подробный лог проверки лежит в [docs/verification.md](docs/verification.md).

## Ещё два экрана

### Навыки из текстов вакансий

Навыки ищутся по явному словарю технологий. Это простой и проверяемый способ,
а не ML-классификация.

![Навыки в требованиях вакансий](docs/images/dashboard-skills.jpg)

### Аудит загрузки

Здесь видны исходное число строк, результат фильтрации, число API-запросов и
статус каждого поискового сегмента.

![Контроль последней загрузки](docs/images/dashboard-quality.jpg)

## Как устроен проект

```mermaid
flowchart LR
    HH[HeadHunter API] --> PY[Python loader]
    TV[Работа России API] --> PY
    PY --> FILES[RAW JSONL]
    PY --> RAW[(raw)]
    PY --> AUDIT[(audit)]
    RAW --> STG[stg views]
    STG --> DWH[(dwh)]
    DWH --> MART[(mart)]
    MART --> UI[Streamlit]
```

- `raw` хранит общую модель и обезличенные поля источника;
- `audit` хранит запуски, запросы, ошибки и поисковые сегменты;
- `stg` приводит JSON-поля к нужным типам;
- `dwh` хранит измерения, связи и историю снимков;
- `mart` готовит данные для запросов и дашборда.

Если загружены оба источника, `mart.v_current_vacancies` берёт последний
успешный снимок каждого из них. Поэтому более свежий запуск одного API не
скрывает данные второго. Вымышленный sample-набор показывается только тогда,
когда в базе ещё нет ни одного живого источника.

Отдельно можно посмотреть [описание архитектуры](docs/architecture.md),
[ER-модель](docs/er-model.md) и [правила расчётов](docs/methodology.md).

## SQL

Основная часть проекта находится в PostgreSQL. Несколько примеров:

- [топ навыков с DENSE_RANK](sql/analytics/01_top_skills_by_job_group.sql);
- [изменение по неделям с LAG](sql/analytics/02_weekly_new_vacancies.sql);
- [работодатели в трёх направлениях](sql/analytics/03_employers_in_three_directions.sql);
- [медианная зарплата через PERCENTILE_CONT](sql/analytics/04_median_salary_by_group_region.sql);
- [сравнение снимков через FULL OUTER JOIN](sql/analytics/05_snapshot_diff.sql);
- [зарплата с выбранным навыком и без него](sql/analytics/06_salary_with_and_without_skill.sql);
- [частые пары навыков](sql/analytics/07_frequent_skill_pairs.sql);
- [EXPLAIN ANALYZE и индексы](sql/analytics/08_explain_optimization.sql).

## Как запустить

Нужны Python 3.9+, Docker и Docker Compose.

```bash
git clone https://github.com/us6fu1/it-job-market-observatory.git
cd it-job-market-observatory

python3 -m venv .venv
source .venv/bin/activate
pip install -e .

cp .env.example .env
docker compose up -d postgres
export DATABASE_URL='postgresql://job_market:change_me@localhost:5432/job_market'
python scripts/run_sql.py ddl
```

Живая загрузка без регистрации и токена:

```bash
python -m ingestion collect-trudvsem \
  --config config/trudvsem_segments.json \
  --raw-dir data/raw-trudvsem \
  --database-url "$DATABASE_URL"

python scripts/run_sql.py load
python scripts/run_sql.py quality
python -m streamlit run dashboard/app.py
```

После запуска дашборд будет доступен на
[http://localhost:8501](http://localhost:8501).

### Проверка без интернета

```bash
python -m unittest discover -s tests/unit -v
python -m ingestion sample --input data/sample --output build/sample
python scripts/load_sample_to_postgres.py
python scripts/run_sql.py load
python scripts/run_sql.py quality
```

Ту же проверку PostgreSQL после запуска контейнера можно выполнить короче:

```bash
make db-verify
```

Данные в `data/sample` вымышлены и нужны только для воспроизводимой проверки.

<details>
<summary><strong>Запуск HeadHunter</strong></summary>

```bash
export HH_USER_AGENT='IT-Job-Market-Observatory/0.2 (contact: email@example.com)'
export HH_ACCESS_TOKEN='token'

python -m ingestion collect \
  --config config/search_segments.example.json \
  --raw-dir data/raw \
  --database-url "$DATABASE_URL"
```

Токены, `.env` и RAW-файлы не должны попадать в Git.

</details>

## Структура папок

```text
ingestion/          API-клиенты и загрузка данных
sql/ddl/            таблицы, представления и индексы
sql/staging/        перенос данных в DWH
sql/analytics/      аналитические запросы
tests/unit/         тесты Python
tests/data_quality/ проверки данных в PostgreSQL
dashboard/          приложение Streamlit
docs/               архитектура и методика
data/sample/        небольшой вымышленный набор
```

## Ограничения

- история начинается с первого запуска;
- окно «Работы России» считается по дате изменения записи;
- текстовый поиск даёт много шума и требует фильтрации;
- извлечение навыков зависит от небольшого словаря;
- исчезновение из выдачи не доказывает закрытие вакансии;
- медиана зарплаты считается только для вилок с обеими границами.

Чтобы делать выводы о динамике рынка, нужно накопить несколько последовательных
снимков. Сейчас проект уже показывает работу загрузки, модели данных, SQL и
контроля качества.
