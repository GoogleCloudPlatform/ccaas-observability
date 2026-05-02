-- CCAIP Activity Logs Query
-- Description: Fetches activity logs for the last 14 days sorted from old to new.

SELECT
  FORMAT_TIMESTAMP('%Y-%m-%d %H:%M:%E*S', timestamp) as timestamp,
  JSON_VALUE(resource.labels, '$.resource_container') as ccaas_project_id,
  JSON_VALUE(resource.labels, '$.location') as ccaas_location,
  JSON_VALUE(resource.labels, '$.resource_id') as ccaas_id,
  JSON_VALUE(labels, '$.tracker_id') as interaction_id,
  text_payload as core_message
FROM
  `<PROJECT_ID>.<DATASET>._AllLogs`
WHERE
  log_name LIKE "%/logs/contactcenteraiplatform.googleapis.com%2Factivity"
  AND timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 14 DAY)
ORDER BY
  timestamp ASC;
