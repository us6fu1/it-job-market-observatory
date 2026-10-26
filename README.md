# IT Job Market Observatory

[![CI](https://github.com/us6fu1/it-job-market-observatory/actions/workflows/ci.yml/badge.svg)](https://github.com/us6fu1/it-job-market-observatory/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)
![Tests](https://img.shields.io/badge/unit_tests-34_passed-16a34a)

ETL-проект для наблюдения за вакансиями Data Analyst, BI Developer и Data
Engineer. Он получает данные из REST API, сохраняет обезличенный снимок полей
источника вместе с общей моделью, очищает шумную поисковую выдачу, строит слои
RAW/STG/DWH/MART в PostgreSQL и показывает результат в Streamlit-дашборде.

Проект можно проверить без токенов. Для живой загрузки используется открытый
API «Работа России», а для полностью воспроизводимого запуска есть небольшой
набор вымышленных данных.

![Превью дашборда IT Job Market Observatory](docs/images/dashboard-preview.svg)

## Что здесь можно посмотреть

- два источника данных с общей внутренней моделью: HeadHunter и «Работа России»;
- загрузчик с повторными попытками, аудитом HTTP-запросов и защитой от дублей;
- очистку нерелевантных результатов по прозрачным правилам заголовков;
- PostgreSQL-модель со снимками вакансий, навыками, регионами и работодателями;
- аналитический SQL с `JOIN`, CTE, `DENSE_RANK`, `LAG`, `FULL OUTER JOIN`,
  `PERCENTILE_CONT` и `EXPLAIN ANALYZE`;
- SQL-проверки качества данных и 34 модульных теста;
- CI в GitHub Actions с PostgreSQL, SQL-проверками и запуском через Docker Compose;
- дашборд с общими фильтрами для показателей, вакансий, навыков и динамики.

## Проверенный живой запуск

26 октября 2026 года конвейер был полностью проверен на открытом API «Работа
России». В выборку вошли записи, которые источник изменял в течение последних
90 дней. Дата публикации вакансии при этом могла быть более ранней.

| Показатель | Результат |
| --- | ---: |
| Строк проверено в поисковой выдаче | 958 |
| Отсеяно как нерелевантные по названию | 912 |
| Принято строк после фильтра | 46 |
| Уникальных профильных вакансий | 36 |
| Работодателей | 22 |
| Регионов | 13 |
| Вакансий с указанной зарплатой | 33 из 36 |
| Ошибок в шести SQL-проверках качества | 0 |

Этот срез доказывает, что конвейер работает на настоящем API, но не выдаётся за
полную статистику российского IT-рынка. У источника другой состав работодателей,
а полнота текстовых навыков ниже, чем у специализированных сайтов с вакансиями.
Подробности и команды проверки собраны в
[docs/verification.md](docs/verification.md).

## Архитектура

```mermaid
flowchart LR
    Sources[REST API] --> Loader[Python ingestion]
    Loader --> Files[RAW JSONL]
    Loader --> Raw[(raw)]
    Loader --> Audit[(audit)]
    Raw --> Stg[stg views]
    Stg --> Dwh[(dwh)]
    Dwh --> Mart[(mart)]
    Mart --> Dashboard[Streamlit]
```

- `raw` хранит общую модель и обезличенный снимок исходных полей. Контакты из
  открытого ответа намеренно не переносятся.
- `audit` фиксирует запуски, запросы, ошибки и поисковые сегменты.
- `stg` извлекает типизированные поля из JSON.
- `dwh` хранит измерения, связи и исторические снимки.
- `mart` содержит готовые показатели для SQL-анализа и дашборда.

Полная схема есть в [docs/architecture.md](docs/architecture.md), ER-модель - в
[docs/er-model.md](docs/er-model.md), правила расчётов - в
[docs/methodology.md](docs/methodology.md).

## Быстрый запуск

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

Живая загрузка из открытого API без регистрации и токена:

```bash
python -m ingestion collect-trudvsem \
  --config config/trudvsem_segments.json \
  --raw-dir data/raw-trudvsem \
  --database-url "$DATABASE_URL"
python scripts/run_sql.py load
python scripts/run_sql.py quality
python -m streamlit run dashboard/app.py
```

Дашборд откроется на `http://localhost:8501`. Сырые выгрузки сохраняются только
локально и исключены из Git.

## Проверка без интернета

```bash
python -m unittest discover -s tests/unit -v
python -m ingestion sample --input data/sample --output build/sample
python scripts/load_sample_to_postgres.py
python scripts/run_sql.py load
python scripts/run_sql.py quality
```

Файлы в `data/sample` вымышлены. Дашборд явно помечает такой режим и не смешивает
его с живыми данными.

## HeadHunter

Адаптер HeadHunter сохранён как отдельный источник. Он умеет делить поисковые
сегменты, контролировать ограничение в 2 000 результатов и загружать детальные
карточки. Для устойчивого поиска нужен OAuth-токен одобренного API-приложения,
поэтому проект не притворяется, что токен доступен всем.

Если одобренный токен есть, запуск выглядит так:

```bash
export HH_USER_AGENT='IT-Job-Market-Observatory/0.2 (contact: email@example.com)'
export HH_ACCESS_TOKEN='token'
python -m ingestion collect \
  --config config/search_segments.example.json \
  --raw-dir data/raw \
  --database-url "$DATABASE_URL"
```

Токены, `.env` и сырые ответы API нельзя добавлять в Git.

## Структура проекта

```text
ingestion/          API-клиенты, сегментация, очистка и RAW-загрузка
sql/ddl/            схемы, таблицы, представления и индексы
sql/staging/        перенос данных из STG в DWH
sql/analytics/      аналитические запросы
tests/unit/         модульные тесты
tests/data_quality/ SQL-проверки качества
dashboard/          Streamlit-дашборд
docs/               архитектура, методика и результаты проверки
data/sample/        воспроизводимый набор вымышленных ответов
```

## Ограничения

- История начинается с первого запуска проекта.
- Окно «Работы России» задаётся по дате изменения записи в источнике, а не по
  дате первоначальной публикации. График новых публикаций использует отдельное
  поле `published_at` и ограничивается тем же календарным окном.
- «Работа России» ищет по тексту шире ожидаемого, поэтому после API применяется
  отдельный фильтр названий. Все правила лежат в конфигурации и видны в аудите.
- Навыки источника заполнены не всегда. Недостающие технологии извлекаются из
  текста только по явному словарю, без догадок модели.
- Исчезновение вакансии из поиска не считается доказательством её закрытия.
- Зарплатная статистика не строится по вакансиям без обеих границ вилки.
