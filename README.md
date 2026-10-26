<div align="center">

# IT Job Market Observatory

**ETL-проект для наблюдения за вакансиями Data Analyst, BI Developer и Data Engineer**

Python загружает и очищает данные из REST API, PostgreSQL строит слои
RAW/STG/DWH/MART, а Streamlit превращает витрины в интерактивный дашборд.

[![CI](https://github.com/us6fu1/it-job-market-observatory/actions/workflows/ci.yml/badge.svg)](https://github.com/us6fu1/it-job-market-observatory/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-dashboard-FF4B4B?logo=streamlit&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![Tests](https://img.shields.io/badge/unit_tests-34_passed-16a34a)

</div>

![Превью дашборда IT Job Market Observatory](docs/images/dashboard-preview.svg)

## Результат живого запуска

Проверенный прогон выполнен **26 октября 2026 года** на открытом API
«Работа России». Источник вернул записи, которые изменялись в течение последних
90 дней.

| 36 вакансий | 22 работодателя | 13 регионов | 92% с зарплатой |
| :---: | :---: | :---: | :---: |
| после очистки | уникальных компаний | в актуальном снимке | 33 из 36 вакансий |

```text
Строк проверено             958
Отсеяно по названию         912
Принято строк                46
Уникальных вакансий          36
Ошибок API                    0
Ошибок SQL-проверок           0
```

> Это проверка настоящего ETL-конвейера, а не полная статистика российского
> IT-рынка. Период API ограничивает дату изменения записи, а первоначальная дата
> публикации может быть более ранней.

[Подробный протокол проверки](docs/verification.md)

## Что реализовано

| Задача | Решение |
| --- | --- |
| Источники | HeadHunter и открытый API «Работа России» с общей внутренней моделью |
| Надёжная загрузка | Повторные попытки, обработка 429/5xx, таймауты и аудит запросов |
| Контроль объёма | Деление поисковых сегментов и явная фиксация превышения лимита |
| Качество выдачи | Настраиваемые фильтры заголовков и удаление дублей по `vacancy_id` |
| Безопасный RAW | Каноническая запись и обезличенная копия полей источника без контактов |
| Хранилище | PostgreSQL 16 со слоями `raw`, `stg`, `dwh`, `mart` и `audit` |
| Аналитика | Навыки, зарплаты, регионы, работодатели и публикации по неделям |
| Проверки | 34 unit-теста, 6 SQL-проверок и CI с настоящим PostgreSQL |
| Визуализация | Streamlit-дашборд с общими фильтрами и аудитом последней загрузки |

## Архитектура

```mermaid
flowchart LR
    HH[HeadHunter API]
    TV[Работа России API]
    PY[Python ingestion]
    FILES[RAW JSONL]
    RAW[(raw)]
    AUDIT[(audit)]
    STG[stg views]
    DWH[(dwh)]
    MART[(mart)]
    UI[Streamlit]

    HH --> PY
    TV --> PY
    PY --> FILES
    PY --> RAW
    PY --> AUDIT
    RAW --> STG --> DWH --> MART --> UI
```

- `raw` хранит общую модель и обезличенный снимок исходных полей;
- `audit` фиксирует запуски, HTTP-запросы, ошибки и поисковые сегменты;
- `stg` извлекает и приводит JSON-поля к нужным типам;
- `dwh` хранит измерения, связи и исторические снимки вакансий;
- `mart` готовит показатели для SQL-анализа и дашборда.

Документы: [архитектура](docs/architecture.md) ·
[ER-модель](docs/er-model.md) · [методика расчётов](docs/methodology.md)

## SQL-витрина проекта

В репозитории есть отдельные запросы, которые можно обсуждать на собеседовании:

- [топ навыков по профессиям с DENSE_RANK](sql/analytics/01_top_skills_by_job_group.sql);
- [недельная динамика с LAG](sql/analytics/02_weekly_new_vacancies.sql);
- [работодатели сразу в трёх направлениях](sql/analytics/03_employers_in_three_directions.sql);
- [медианная зарплата через PERCENTILE_CONT](sql/analytics/04_median_salary_by_group_region.sql);
- [сравнение двух снимков через FULL OUTER JOIN](sql/analytics/05_snapshot_diff.sql);
- [зарплата вакансий с выбранным навыком и без него](sql/analytics/06_salary_with_and_without_skill.sql);
- [часто встречающиеся пары навыков](sql/analytics/07_frequent_skill_pairs.sql);
- [пример оптимизации с EXPLAIN ANALYZE](sql/analytics/08_explain_optimization.sql).

## Быстрый запуск

Понадобятся Python 3.9+, Docker и Docker Compose.

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

### Живые данные без токена

```bash
python -m ingestion collect-trudvsem \
  --config config/trudvsem_segments.json \
  --raw-dir data/raw-trudvsem \
  --database-url "$DATABASE_URL"

python scripts/run_sql.py load
python scripts/run_sql.py quality
python -m streamlit run dashboard/app.py
```

Дашборд откроется на [http://localhost:8501](http://localhost:8501). RAW-файлы
сохраняются только локально и исключены из Git.

### Воспроизводимая проверка без интернета

```bash
python -m unittest discover -s tests/unit -v
python -m ingestion sample --input data/sample --output build/sample
python scripts/load_sample_to_postgres.py
python scripts/run_sql.py load
python scripts/run_sql.py quality
```

Файлы в `data/sample` полностью вымышлены. Дашборд помечает такой режим и не
смешивает его с результатами живого API.

<details>
<summary><strong>Запуск адаптера HeadHunter</strong></summary>

Для устойчивого поиска нужен OAuth-токен одобренного API-приложения. Без токена
можно запускать sample data и открытый источник «Работа России».

```bash
export HH_USER_AGENT='IT-Job-Market-Observatory/0.2 (contact: email@example.com)'
export HH_ACCESS_TOKEN='token'

python -m ingestion collect \
  --config config/search_segments.example.json \
  --raw-dir data/raw \
  --database-url "$DATABASE_URL"
```

Токены, `.env` и RAW-ответы нельзя добавлять в Git.

</details>

## Структура

```text
ingestion/          API-клиенты, сегментация, очистка и RAW-загрузка
sql/ddl/            схемы, таблицы, ограничения и индексы
sql/staging/        преобразование STG → DWH
sql/analytics/      показательные аналитические запросы
tests/unit/         модульные тесты Python
tests/data_quality/ проверки данных в PostgreSQL
dashboard/          Streamlit-дашборд
docs/               архитектура, методика и результаты проверки
data/sample/        воспроизводимый набор вымышленных ответов
```

## Ограничения исследования

- история начинается с первого запуска проекта;
- окно «Работы России» задаётся по дате изменения записи, а не первоначальной
  публикации;
- текстовый поиск источника даёт много шума, поэтому применяется отдельный
  фильтр заголовков;
- навыки дополняются только по явному словарю технологий, без ML-классификации;
- исчезновение из поиска не считается доказательством закрытия вакансии;
- медианная зарплата рассчитывается только по вилкам с обеими границами.

Проект показывает инженерный конвейер и качество обработки данных. Для выводов
о динамике рынка нужно накопить несколько последовательных снимков.
