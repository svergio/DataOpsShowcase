{{ config(
    materialized='incremental',
    incremental_strategy='append',
    unique_key='hub_key',
    on_schema_change='append_new_columns',
    tags=['vault', 'rdv', 'hub'],
    indexes=[
        {'columns': ['hub_key'], 'unique': True},
        {'columns': ['business_key'], 'unique': True}
    ]
) }}

{{ hub_incremental(
    source_relation=ref('stg_payments'),
    business_key_column='payment_bk'
) }}
