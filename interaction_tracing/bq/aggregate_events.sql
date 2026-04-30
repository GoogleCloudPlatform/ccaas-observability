-- Aggregate Interaction Logs Query
-- Description: Combines logs from all 4 sources for the last 14 days, sorted from old to new.
-- Enriches Dialogflow logs with CCAAS identifiers via the mapping from Script 5.

WITH mapping AS (
  WITH ccaip_mapping AS (
    SELECT
      JSON_VALUE(resource.labels, '$.resource_container') as ccaas_project_id,
      JSON_VALUE(resource.labels, '$.location') as ccaas_location,
      JSON_VALUE(resource.labels, '$.resource_id') as ccaas_id,
      COALESCE(
        JSON_VALUE(json_payload, '$.event.payload.participant.call_id'),
        CASE 
          WHEN JSON_VALUE(json_payload, '$.event.payload.call.id') IS NOT NULL 
          THEN 
            IF(STARTS_WITH(JSON_VALUE(json_payload, '$.event.payload.call.id'), 'call_'), 
               JSON_VALUE(json_payload, '$.event.payload.call.id'), 
               CONCAT('call_', JSON_VALUE(json_payload, '$.event.payload.call.id')))
          ELSE NULL 
        END,
        CASE 
          WHEN JSON_VALUE(json_payload, '$.event.payload.chat.id') IS NOT NULL 
          THEN 
            IF(STARTS_WITH(JSON_VALUE(json_payload, '$.event.payload.chat.id'), 'chat_'), 
               JSON_VALUE(json_payload, '$.event.payload.chat.id'), 
               CONCAT('chat_', JSON_VALUE(json_payload, '$.event.payload.chat.id')))
          ELSE NULL 
        END,
        JSON_VALUE(labels, '$.tracker_id')
      ) as interaction_id,
      JSON_VALUE(json_payload, '$.event.payload.participant.df_conversation_id') as df_conversation_id
    FROM
      `<PROJECT_ID>.<DATASET>._AllLogs`
    WHERE
      log_name LIKE "%/logs/contactcenteraiplatform.googleapis.com%2Fevents"
      AND JSON_VALUE(json_payload, '$.event.name') = "dialogflow_conversation_created"
      AND timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 14 DAY)
  ),
  df_audit AS (
    SELECT
      REGEXP_EXTRACT(proto_payload.audit_log.resource_name, r'projects/([^/]+)') as df_project_id,
      REGEXP_EXTRACT(proto_payload.audit_log.resource_name, r'locations/([^/]+)') as df_location,
      REGEXP_EXTRACT(proto_payload.audit_log.resource_name, r'conversations/([a-zA-Z0-9_-]+)') as df_conversation_id
    FROM
      `<PROJECT_ID>.<DATASET>._AllLogs`
    WHERE
      log_name LIKE "%/logs/cloudaudit.googleapis.com%2Fdata_access"
      AND proto_payload.audit_log.service_name = "dialogflow.googleapis.com"
      AND timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 14 DAY)
  )
  SELECT DISTINCT
    m.ccaas_project_id,
    m.ccaas_location,
    m.ccaas_id,
    m.interaction_id,
    a.df_project_id,
    a.df_location,
    m.df_conversation_id
  FROM
    ccaip_mapping m
  LEFT JOIN
    df_audit a
  ON
    m.df_conversation_id = a.df_conversation_id
),
ccaip_activity AS (
  SELECT
    timestamp,
    'CCAAS_ACTIVITY' as source,
    JSON_VALUE(resource.labels, '$.resource_container') as ccaas_project_id,
    JSON_VALUE(resource.labels, '$.location') as ccaas_location,
    JSON_VALUE(resource.labels, '$.resource_id') as ccaas_id,
    JSON_VALUE(labels, '$.tracker_id') as interaction_id,
    CAST(NULL AS STRING) as df_project_id,
    CAST(NULL AS STRING) as df_location,
    CAST(NULL AS STRING) as df_conversation_id,
    text_payload as core_message
  FROM
    `<PROJECT_ID>.<DATASET>._AllLogs`
  WHERE
    log_name LIKE "%/logs/contactcenteraiplatform.googleapis.com%2Factivity"
    AND timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 14 DAY)
),
ccaip_events AS (
  SELECT
    timestamp,
    'CCAAS_EVENT' as source,
    JSON_VALUE(resource.labels, '$.resource_container') as ccaas_project_id,
    JSON_VALUE(resource.labels, '$.location') as ccaas_location,
    JSON_VALUE(resource.labels, '$.resource_id') as ccaas_id,
    COALESCE(
      JSON_VALUE(json_payload, '$.event.payload.participant.call_id'),
      CASE 
        WHEN JSON_VALUE(json_payload, '$.event.payload.call.id') IS NOT NULL 
        THEN 
          IF(STARTS_WITH(JSON_VALUE(json_payload, '$.event.payload.call.id'), 'call_'), 
             JSON_VALUE(json_payload, '$.event.payload.call.id'), 
             CONCAT('call_', JSON_VALUE(json_payload, '$.event.payload.call.id')))
        ELSE NULL 
      END,
      CASE 
        WHEN JSON_VALUE(json_payload, '$.event.payload.chat.id') IS NOT NULL 
        THEN 
          IF(STARTS_WITH(JSON_VALUE(json_payload, '$.event.payload.chat.id'), 'chat_'), 
             JSON_VALUE(json_payload, '$.event.payload.chat.id'), 
             CONCAT('chat_', JSON_VALUE(json_payload, '$.event.payload.chat.id')))
        ELSE NULL 
      END,
      JSON_VALUE(labels, '$.tracker_id')
    ) as interaction_id,
    CAST(NULL AS STRING) as df_project_id,
    CAST(NULL AS STRING) as df_location,
    CAST(NULL AS STRING) as df_conversation_id,
    COALESCE(
      JSON_VALUE(json_payload, '$.message'),
      JSON_VALUE(json_payload, '$.event.name'),
      'N/A'
    ) as core_message
  FROM
    `<PROJECT_ID>.<DATASET>._AllLogs`
  WHERE
    log_name LIKE "%/logs/contactcenteraiplatform.googleapis.com%2Fevents"
    AND timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 14 DAY)
),
df_audit_logs AS (
  SELECT
    timestamp,
    'DF_AUDIT' as source,
    REGEXP_EXTRACT(proto_payload.audit_log.resource_name, r'projects/([^/]+)') as df_project_id,
    REGEXP_EXTRACT(proto_payload.audit_log.resource_name, r'locations/([^/]+)') as df_location,
    COALESCE(
      REGEXP_EXTRACT(proto_payload.audit_log.resource_name, r'conversations/([a-zA-Z0-9_-]+)'),
      REGEXP_EXTRACT(TO_JSON_STRING(proto_payload.audit_log.response), r'conversations/([a-zA-Z0-9_-]+)')
    ) as df_conversation_id,
    proto_payload.audit_log.method_name as core_message
  FROM
    `<PROJECT_ID>.<DATASET>._AllLogs`
  WHERE
    log_name LIKE "%/logs/cloudaudit.googleapis.com%2Fdata_access"
    AND proto_payload.audit_log.service_name = "dialogflow.googleapis.com"
    AND timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 14 DAY)
),
df_runtime_logs AS (
  SELECT
    timestamp,
    'DF_RUNTIME' as source,
    JSON_VALUE(resource.labels, '$.project_id') as df_project_id,
    JSON_VALUE(labels, '$.location_id') as df_location,
    JSON_VALUE(labels, '$.session_id') as df_conversation_id,
    CONCAT(
      CASE 
        WHEN JSON_QUERY(json_payload, '$.queryInput') IS NOT NULL THEN 'REQ: '
        WHEN JSON_QUERY(json_payload, '$.queryResult') IS NOT NULL THEN 'RESP: '
        WHEN JSON_VALUE(json_payload, '$.code') IS NOT NULL THEN 'ERR: '
        ELSE 'OP: '
      END,
      CASE 
        WHEN JSON_VALUE(json_payload, '$.queryInput.audio') IS NOT NULL THEN '<AUDIO> '
        ELSE ''
      END,
      COALESCE(
        -- For Response logs
        CASE 
          WHEN JSON_QUERY(json_payload, '$.queryResult') IS NOT NULL 
          THEN CONCAT(
            'Text="', COALESCE(JSON_VALUE(json_payload, '$.queryResult.queryText'), 'N/A'), '"',
            ' Intent="', COALESCE(JSON_VALUE(json_payload, '$.queryResult.intent.displayName'), 'N/A'), '"'
          )
          ELSE NULL
        END,
        -- For Request logs with text
        CASE WHEN JSON_VALUE(json_payload, '$.queryInput.text.text') IS NOT NULL THEN CONCAT('Text="', JSON_VALUE(json_payload, '$.queryInput.text.text'), '"') ELSE NULL END,
        -- For Request logs with event
        CASE WHEN JSON_VALUE(json_payload, '$.queryInput.event.event') IS NOT NULL THEN CONCAT('Event="', JSON_VALUE(json_payload, '$.queryInput.event.event'), '"') ELSE NULL END,
        -- For Request logs with DTMF
        CASE WHEN JSON_QUERY(json_payload, '$.queryInput.dtmf') IS NOT NULL THEN CONCAT('DTMF="', COALESCE(JSON_VALUE(json_payload, '$.queryInput.dtmf.digits'), 'EMPTY'), '"') ELSE NULL END,
        -- For Error logs
        CASE WHEN JSON_VALUE(json_payload, '$.code') IS NOT NULL THEN CONCAT('Error="', JSON_VALUE(json_payload, '$.message'), '"') ELSE NULL END,
        'N/A'
      )
    ) as core_message
  FROM
    `<PROJECT_ID>.<DATASET>._AllLogs`
  WHERE
    log_name LIKE "%/logs/dialogflow-runtime.googleapis.com%2Frequests"
    AND timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 14 DAY)
),
combined_df AS (
  SELECT
    d.timestamp,
    d.source,
    m.ccaas_project_id,
    m.ccaas_location,
    m.ccaas_id,
    m.interaction_id,
    d.df_project_id,
    d.df_location,
    d.df_conversation_id,
    d.core_message
  FROM (
    SELECT timestamp, source, df_project_id, df_location, df_conversation_id, core_message FROM df_audit_logs
    UNION ALL
    SELECT timestamp, source, df_project_id, df_location, df_conversation_id, core_message FROM df_runtime_logs
  ) d
  LEFT JOIN
    mapping m
  ON
    d.df_conversation_id = m.df_conversation_id
)
SELECT
  FORMAT_TIMESTAMP('%Y-%m-%d %H:%M:%E*S', timestamp) as timestamp,
  source,
  ccaas_project_id,
  ccaas_location,
  ccaas_id,
  interaction_id,
  df_project_id,
  df_location,
  df_conversation_id,
  core_message
FROM (
  SELECT timestamp, source, ccaas_project_id, ccaas_location, ccaas_id, interaction_id, df_project_id, df_location, df_conversation_id, core_message FROM ccaip_activity
  UNION ALL
  SELECT timestamp, source, ccaas_project_id, ccaas_location, ccaas_id, interaction_id, df_project_id, df_location, df_conversation_id, core_message FROM ccaip_events
  UNION ALL
  SELECT timestamp, source, ccaas_project_id, ccaas_location, ccaas_id, interaction_id, df_project_id, df_location, df_conversation_id, core_message FROM combined_df
)
ORDER BY
  timestamp ASC;
