/**
 * Copyright 2026 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

resource "google_monitoring_dashboard" "platform_dashboard" {
  dashboard_json = jsonencode({
    displayName = "CCaaS - Platform"
    mosaicLayout = {
      columns = 48
      tiles = [
        {
          height = 8
          width  = 16
          widget = {
            title = "CCaaS Platform Updates"
            scorecard = {
              sparkChartView = {
                sparkChartType = "SPARK_BAR"
              }
              timeSeriesQuery = {
                outputFullDuration = true
                timeSeriesFilter = {
                  aggregation = {
                    alignmentPeriod    = "86400s"
                    crossSeriesReducer = "REDUCE_SUM"
                    perSeriesAligner   = "ALIGN_DELTA"
                  }
                  filter = "metric.type=\"logging.googleapis.com/user/ccaas_version_updates\" resource.type=\"logging_bucket\""
                }
              }
            }
          }
        },
        {
          height = 16
          width  = 48
          yPos   = 8
          widget = {
            title = "CCaaS Platform Updates by Version"
            xyChart = {
              chartOptions = {
                mode = "COLOR"
              }
              dataSets = [
                {
                  legendTemplate     = "$${metric.labels.version} ($${metric.labels.domain_prefix})"
                  minAlignmentPeriod = "3600s"
                  plotType           = "STACKED_BAR"
                  targetAxis         = "Y1"
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      aggregation = {
                        alignmentPeriod    = "3600s"
                        crossSeriesReducer = "REDUCE_SUM"
                        groupByFields = [
                          "metric.label.version",
                          "metric.label.domain_prefix"
                        ]
                        perSeriesAligner = "ALIGN_DELTA"
                      }
                      filter = "metric.type=\"logging.googleapis.com/user/ccaas_version_updates\" resource.type=\"logging_bucket\""
                    }
                  }
                }
              ]
              yAxis = {
                scale = "LINEAR"
              }
            }
          }
        },
        {
          height = 16
          width  = 48
          yPos   = 24
          widget = {
            title = "Platform Updates Log Analytics Table"
            timeSeriesTable = {
              metricVisualization = "NUMBER"
              dataSets = [
                {
                  timeSeriesQuery = {
                    opsAnalyticsQuery = {
                      sql = <<-EOT
                        SELECT
                          FORMAT_TIMESTAMP('%Y-%m-%d %H:%M:%E*S', timestamp) as timestamp,
                          JSON_VALUE(resource.labels, '$.location') as location,
                          JSON_VALUE(resource.labels, '$.resource_id') as instance_id,
                          JSON_VALUE(json_payload, '$.event.payload.domain_prefix') as domain_prefix,
                          JSON_VALUE(json_payload, '$.event.payload.version') as version,
                          JSON_VALUE(json_payload, '$.message') as message
                        FROM
                          `${var.project_id}.${var.log_bucket.location}.${var.log_bucket.name}._AllLogs`
                        WHERE
                          log_name LIKE "%/logs/contactcenteraiplatform.googleapis.com%2Factivity"
                          AND JSON_VALUE(json_payload, '$.message') LIKE "Contact Center as a Service update finished. Updated to version%"
                        ORDER BY
                          timestamp DESC;
                      EOT
                    }
                  }
                }
              ]
            }
          }
        }
      ]
    }
  })

  project = var.project_id
}
