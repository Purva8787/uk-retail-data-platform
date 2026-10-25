select
    md5(postcode_area)                                   as region_key,
    postcode_area,
    region,
    nation,
    delivery_band,
    delivery_band <> 'mainland'                          as is_surcharge_zone,
    case nation
        when 'Scotland' then 'scotland'
        when 'Northern Ireland' then 'northern-ireland'
        else 'england-and-wales'
    end                                                  as bank_holiday_division
from {{ ref('stg_postcode_areas') }}
