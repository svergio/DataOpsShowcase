{#
  build_pit — generates a Point-in-Time table SQL for a hub.

  Strategy (Postgres-friendly, deterministic):
    * Build an `as_of_dates` spine — daily grain by default, derived from
      max(load_dts) of the hub satellites and the configured lookback window.
    * For each hub_key x as_of_date, find the active satellite version
      (effective_from <= as_of_date AND (effective_to > as_of_date OR effective_to IS NULL)).
    * Materialise (hub_key, as_of_date, sat_<n>_load_dts, sat_<n>_hashdiff, sat_<n>_effective_from)
      so consumers can join PIT once and pick a snapshot quickly.

  Args:
    hub_relation        : ref('hub_*')
    satellite_specs     : list of dicts: [{name: 'sat_*', alias: 'sat_customer_details'}, ...]
    as_of_strategy      : 'daily' (default) — produces 1 row per day per hub_key
    lookback_days       : how many days back to populate (default 90)
#}
{% macro build_pit(hub_relation, satellite_specs, as_of_strategy='daily', lookback_days=90) -%}
WITH spine AS (
    SELECT generate_series(
        date_trunc('day', NOW()) - INTERVAL '{{ lookback_days }} day',
        date_trunc('day', NOW()),
        INTERVAL '1 day'
    ) AS as_of_date
),
hubs AS (
    SELECT hub_key
    FROM {{ hub_relation }}
),
hub_dates AS (
    SELECT h.hub_key, s.as_of_date
    FROM hubs h
    CROSS JOIN spine s
)
SELECT
    hd.hub_key,
    hd.as_of_date
    {% for sat in satellite_specs %}
        , (
            SELECT s.load_dts
            FROM {{ sat.relation }} s
            WHERE s.hub_key = hd.hub_key
              AND s.effective_from <= hd.as_of_date + INTERVAL '1 day' - INTERVAL '1 second'
              AND (s.effective_to IS NULL OR s.effective_to > hd.as_of_date + INTERVAL '1 day' - INTERVAL '1 second')
            ORDER BY s.effective_from DESC, s.load_dts DESC
            LIMIT 1
        ) AS {{ sat.alias }}_load_dts
        , (
            SELECT s.hashdiff
            FROM {{ sat.relation }} s
            WHERE s.hub_key = hd.hub_key
              AND s.effective_from <= hd.as_of_date + INTERVAL '1 day' - INTERVAL '1 second'
              AND (s.effective_to IS NULL OR s.effective_to > hd.as_of_date + INTERVAL '1 day' - INTERVAL '1 second')
            ORDER BY s.effective_from DESC, s.load_dts DESC
            LIMIT 1
        ) AS {{ sat.alias }}_hashdiff
        , (
            SELECT s.effective_from
            FROM {{ sat.relation }} s
            WHERE s.hub_key = hd.hub_key
              AND s.effective_from <= hd.as_of_date + INTERVAL '1 day' - INTERVAL '1 second'
              AND (s.effective_to IS NULL OR s.effective_to > hd.as_of_date + INTERVAL '1 day' - INTERVAL '1 second')
            ORDER BY s.effective_from DESC, s.load_dts DESC
            LIMIT 1
        ) AS {{ sat.alias }}_effective_from
    {% endfor %}
FROM hub_dates hd
{%- endmacro %}
