-- Dialogflow Audit Logs Query
-- Description: Fetches Dialogflow Audit logs (Data Access) for the last 14 days sorted from old to new.

SELECT
  FORMAT_TIMESTAMP('%Y-%m-%d %H:%M:%E*S', timestamp) as timestamp,
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
ORDER BY
  timestamp ASC;
