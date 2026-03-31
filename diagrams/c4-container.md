# C4 — Container: WeekChef (синхронный / один процесс Backend)

Граница системы, контейнеры внутри и внешние API. Соответствует схеме с **Telegram handler**, **Orchestrator** и двумя БД.

```mermaid
flowchart TB
  User((Пользователь))

  subgraph sys["WeekChef"]
    subgraph db["Databases"]
      PG1[("PostgreSQL\nstate, sessions, inventory")]
      PG2[("PostgreSQL\nrecipes")]
    end
    subgraph be["Backend"]
      TH[Telegram handler]
      OR[Orchestrator]
    end
  end

  TG[Telegram API]
  GCal[Google Calendar API]
  LLM[LLM API]

  User -->|чат| TG
  TG <-->|webhook / long polling| TH
  TH --> OR

  OR -->|читает / пишет| PG1
  OR -->|поиск рецептов по фильтрам| PG2
  OR -->|OAuth / временные слоты| GCal
  OR -->|запросы: диалог, план, рецепты| LLM
```