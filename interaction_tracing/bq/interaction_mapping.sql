-- Interaction Mapping Query
-- Description: Maps between CCAAS Quad and Dialogflow Quad for the last 14 days.
-- This query joins CCAIP event logs with Dialogflow Audit logs to get the full mapping.

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
  m.df_conversation_id = a.df_conversation_id;
