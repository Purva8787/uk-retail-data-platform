select division, holiday_date::date as holiday_date, title
from {{ ref('uk_bank_holidays') }}
