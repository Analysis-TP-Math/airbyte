{{ config(schema="test_normalization", tags=["nested"]) }}
-- Final base SQL model
select
    _airbyte_conflict_stream_name_hashid,
    {{ adapter.quote('group') }},
    description,
    _airbyte_emitted_at,
    _airbyte_conflict_stream_name_child_hashid
from {{ ref('conflict_stream_name_conflict_stream_name_ab3') }}
-- conflict_stream_name at conflict_stream_name/conflict_stream_name from {{ ref('conflict_stream_name') }}

