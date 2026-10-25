{#- UK tax year runs 6 April to 5 April. Returns e.g. '2024/25'. -#}
{% macro uk_tax_year(date_col) -%}
    case
        when {{ date_col }} >= make_date(extract(year from {{ date_col }})::int, 4, 6)
            then extract(year from {{ date_col }})::int || '/' || right((extract(year from {{ date_col }})::int + 1)::text, 2)
        else (extract(year from {{ date_col }})::int - 1) || '/' || right(extract(year from {{ date_col }})::int::text, 2)
    end
{%- endmacro %}

{#- Black Friday = the day after the 4th Thursday of November. -#}
{% macro black_friday(year_expr) -%}
    (make_date({{ year_expr }}, 11, 1)
        + (((4 - extract(dow from make_date({{ year_expr }}, 11, 1))::int + 7) % 7) + 22))
{%- endmacro %}

{#- Uses the custom schema name exactly (core, staging...) instead of prefixing it with the target schema. -#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}{{ target.schema }}{%- else -%}{{ custom_schema_name | trim }}{%- endif -%}
{%- endmacro %}
