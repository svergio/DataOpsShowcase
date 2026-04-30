# Канон бизнес-ключей Data Vault (расширения генератора)

Согласовано с [Generators.md](Generators.md), [diagrams/oltp-er.md](diagrams/oltp-er.md) и raw-таблицами в `services/postgres/init/06_dwh_raw_generators_extensions.sql`.

| Сущность | Hub (логическое имя) | Business key (столбец BK) | Источник raw |
|----------|----------------------|----------------------------|--------------|
| Маркетинг-кампания | hub_campaigns (dbt) | `campaign_bk` = `campaign_id` | raw.oltp_marketing_campaigns |
| SEO ключевое слово | hub_seo_keywords | `keyword_id` | raw.oltp_seo_keywords |
| Feature flag | hub_feature_flags | `flag_key` | raw.oltp_feature_flags |
| Сотрудник | hub_employees | `employee_number` (стабильный бизнес-код) | raw.oltp_employees |
| Проводка GL | hub_gl_entries | `entry_number` | raw.oltp_general_ledger |
| Событие Kafka (extension) | hub_extension_events | `event_bk` = coalesce(`event_id`, `topic:partition:offset`) | raw.kafka_extension_events |

Примечания:

- Для **employees** в OLTP есть и `employee_id`; в DV для демо выбран **employee_number** как устойчивый внешний код (как в DDL UNIQUE).
- События **feature_flag_eval** могут не содержать `event_id` в payload; тогда BK строится от позиции в Kafka.
- Линки и BDV (pit/bridge) к заказам/клиентам — волна 2.3 по необходимости, см. [diagrams/data_vault_flow.md](diagrams/data_vault_flow.md).
