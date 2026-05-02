-- Dialogflow Runtime Logs Query
-- Description: Fetches Dialogflow Runtime logs for the last 14 days sorted from old to new.
-- Composite message includes Direction, Audio flag, Text, Event, DTMF, Error and Intent.

SELECT
  FORMAT_TIMESTAMP('%Y-%m-%d %H:%M:%E*S', timestamp) as timestamp,
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
ORDER BY
  timestamp ASC;
