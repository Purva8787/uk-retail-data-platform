select
    postcode_area,
    region,
    nation,
    case
        when postcode_area in ('IV', 'HS', 'KW', 'ZE') then 'highlands_islands'
        when postcode_area = 'BT' then 'northern_ireland'
        else 'mainland'
    end as delivery_band
from {{ ref('postcode_areas') }}
