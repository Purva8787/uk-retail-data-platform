-- One row per calendar day, 2022-2026, with UK tax year, ISO week and bank holidays per nation.
with days as (
    select d::date as date_day
    from generate_series('2022-01-01'::date, '2026-12-31'::date, interval '1 day') as d
),

holidays as (
    select * from {{ ref('int_bank_holidays_by_date') }}
)

select
    to_char(days.date_day, 'YYYYMMDD')::int                    as date_key,
    days.date_day,
    extract(year from days.date_day)::int                      as calendar_year,
    extract(quarter from days.date_day)::int                   as calendar_quarter,
    to_char(days.date_day, 'YYYY-"Q"Q')                        as year_quarter,
    extract(month from days.date_day)::int                     as month_number,
    to_char(days.date_day, 'Mon')                              as month_name,
    date_trunc('month', days.date_day)::date                   as month_start,
    extract(isoyear from days.date_day)::int                   as iso_year,
    extract(week from days.date_day)::int                      as iso_week,
    extract(isodow from days.date_day)::int                    as iso_day_of_week,
    to_char(days.date_day, 'Dy')                               as day_name,
    extract(isodow from days.date_day) in (6, 7)               as is_weekend,
    {{ uk_tax_year('days.date_day') }}                         as tax_year,
    coalesce(h.is_bank_holiday_england_wales, false)           as is_bank_holiday_england_wales,
    coalesce(h.is_bank_holiday_scotland, false)                as is_bank_holiday_scotland,
    coalesce(h.is_bank_holiday_northern_ireland, false)        as is_bank_holiday_northern_ireland,
    h.holiday_name,
    days.date_day = {{ black_friday('extract(year from days.date_day)::int') }}       as is_black_friday,
    days.date_day = {{ black_friday('extract(year from days.date_day)::int') }} + 3   as is_cyber_monday,
    (extract(month from days.date_day) = 12 and extract(day from days.date_day) between 1 and 24) as is_christmas_run_up
from days
left join holidays h on h.holiday_date = days.date_day
