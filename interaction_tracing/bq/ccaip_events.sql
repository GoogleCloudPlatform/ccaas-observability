-- CCAIP Event Logs Query
-- Description: Fetches event logs for the last 14 days sorted from old to new.

SELECT
  FORMAT_TIMESTAMP('%Y-%m-%d %H:%M:%E*S', timestamp) as timestamp,
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
ORDER BY
  timestamp ASC;
