-- Pivot GOV.UK holidays to one row per date with a flag per division.
select
    holiday_date,
    bool_or(division = 'england-and-wales')                      as is_bank_holiday_england_wales,
    bool_or(division = 'scotland')                               as is_bank_holiday_scotland,
    bool_or(division = 'northern-ireland')                       as is_bank_holiday_northern_ireland,
    string_agg(distinct title, ' / ')                            as holiday_name
from {{ ref('stg_bank_holidays') }}
group by holiday_date
