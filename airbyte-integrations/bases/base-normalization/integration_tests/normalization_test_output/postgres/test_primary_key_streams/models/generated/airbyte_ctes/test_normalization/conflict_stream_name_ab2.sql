{{ config(schema="_airbyte_test_normalization", tags=["top-level-intermediate"]) }}
-- SQL model to cast each column to its adequate SQL type converted from the JSON schema type
select
    cast({{ adapter.quote('id') }} as {{ dbt_utils.type_string() }}) as {{ adapter.quote('id') }},
    conflict_stream_name,
    _airbyte_emitted_at
from {{ ref('conflict_stream_name_ab1') }}
-- conflict_stream_name

