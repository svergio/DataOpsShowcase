{#
  build_bridge — flattens a Link with its Hubs into a query-friendly bridge.

  Args:
    link_relation : ref('link_*')
    hub_specs     : list of dicts:
                    [{ relation: ref('hub_customers'), alias: 'customer', link_fk: 'customer_hub_key' }, ...]

  Output columns:
    bridge_key (sha256 of link_key + hub_keys),
    link_key,
    {alias}_hub_key for each hub,
    load_dts (link load_dts),
    record_source.
#}
{% macro build_bridge(link_relation, hub_specs) -%}
SELECT
    {{ generate_hash_key(['l.link_key'] + (hub_specs | map(attribute='link_fk') | list)) }} AS bridge_key,
    l.link_key,
    {% for h in hub_specs %}
        {{ h.alias }}.hub_key AS {{ h.alias }}_hub_key,
    {% endfor %}
    l.load_dts,
    l.record_source
FROM {{ link_relation }} l
{% for h in hub_specs %}
    INNER JOIN {{ h.relation }} {{ h.alias }}
        ON {{ h.alias }}.hub_key = l.{{ h.link_fk }}
{% endfor %}
{%- endmacro %}
