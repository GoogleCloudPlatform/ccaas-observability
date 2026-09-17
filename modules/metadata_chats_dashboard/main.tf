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

resource "google_monitoring_dashboard" "metadata_chats" {
  dashboard_json = <<EOF
{
    "displayName": "Chats Monitoring (Metadata Logs)",
    "mosaicLayout": {
        "columns": 48,
        "tiles": [
            {
                "height": 16,
                "widget": {
                    "title": "CCaaS Chats Volume (Metadata Logs, in 5 min windows)",
                    "xyChart": {
                        "chartOptions": {
                            "mode": "COLOR"
                        },
                        "dataSets": [
                            {
                                "legendTemplate": "Success",
                                "minAlignmentPeriod": "300s",
                                "plotType": "LINE",
                                "targetAxis": "Y1",
                                "timeSeriesQuery": {
                                    "timeSeriesFilter": {
                                        "aggregation": {
                                            "alignmentPeriod": "300s",
                                            "crossSeriesReducer": "REDUCE_SUM",
                                            "perSeriesAligner": "ALIGN_DELTA"
                                        },
                                        "filter": "metric.type=\"logging.googleapis.com/user/ccaas_metadata_chats_successful\" resource.type=\"logging_bucket\""
                                    }
                                }
                            },
                            {
                                "legendTemplate": "Escalated",
                                "minAlignmentPeriod": "300s",
                                "plotType": "LINE",
                                "targetAxis": "Y1",
                                "timeSeriesQuery": {
                                    "timeSeriesFilter": {
                                        "aggregation": {
                                            "alignmentPeriod": "300s",
                                            "crossSeriesReducer": "REDUCE_SUM",
                                            "perSeriesAligner": "ALIGN_DELTA"
                                        },
                                        "filter": "metric.type=\"logging.googleapis.com/user/ccaas_metadata_chats_escalated\" resource.type=\"logging_bucket\""
                                    }
                                }
                            },
                            {
                                "legendTemplate": "Abandoned",
                                "minAlignmentPeriod": "300s",
                                "plotType": "LINE",
                                "targetAxis": "Y1",
                                "timeSeriesQuery": {
                                    "timeSeriesFilter": {
                                        "aggregation": {
                                            "alignmentPeriod": "300s",
                                            "crossSeriesReducer": "REDUCE_SUM",
                                            "perSeriesAligner": "ALIGN_DELTA"
                                        },
                                        "filter": "metric.type=\"logging.googleapis.com/user/ccaas_metadata_chats_abandoned\" resource.type=\"logging_bucket\""
                                    }
                                }
                            },
                            {
                                "legendTemplate": "Failed",
                                "minAlignmentPeriod": "300s",
                                "plotType": "LINE",
                                "targetAxis": "Y1",
                                "timeSeriesQuery": {
                                    "timeSeriesFilter": {
                                        "aggregation": {
                                            "alignmentPeriod": "300s",
                                            "crossSeriesReducer": "REDUCE_SUM",
                                            "perSeriesAligner": "ALIGN_DELTA"
                                        },
                                        "filter": "metric.type=\"logging.googleapis.com/user/ccaas_metadata_chats_failed\" resource.type=\"logging_bucket\""
                                    }
                                }
                            }
                        ],
                        "timeshiftDuration": "86400s",
                        "yAxis": {
                            "scale": "LINEAR"
                        }
                    }
                },
                "width": 24
            },
            {
                "height": 16,
                "widget": {
                    "title": "Chat Queue Wait Duration (p50 & p95, in seconds)",
                    "xyChart": {
                        "chartOptions": {
                            "mode": "COLOR"
                        },
                        "dataSets": [
                            {
                                "legendTemplate": "Wait Duration p50",
                                "minAlignmentPeriod": "300s",
                                "plotType": "LINE",
                                "targetAxis": "Y1",
                                "timeSeriesQuery": {
                                    "timeSeriesFilter": {
                                        "aggregation": {
                                            "alignmentPeriod": "300s",
                                            "crossSeriesReducer": "REDUCE_PERCENTILE_50",
                                            "perSeriesAligner": "ALIGN_PERCENTILE_50"
                                        },
                                        "filter": "metric.type=\"logging.googleapis.com/user/ccaas_metadata_chat_wait_duration\" resource.type=\"logging_bucket\""
                                    }
                                }
                            },
                            {
                                "legendTemplate": "Wait Duration p95",
                                "minAlignmentPeriod": "300s",
                                "plotType": "LINE",
                                "targetAxis": "Y1",
                                "timeSeriesQuery": {
                                    "timeSeriesFilter": {
                                        "aggregation": {
                                            "alignmentPeriod": "300s",
                                            "crossSeriesReducer": "REDUCE_PERCENTILE_95",
                                            "perSeriesAligner": "ALIGN_PERCENTILE_95"
                                        },
                                        "filter": "metric.type=\"logging.googleapis.com/user/ccaas_metadata_chat_wait_duration\" resource.type=\"logging_bucket\""
                                    }
                                }
                            }
                        ],
                        "yAxis": {
                            "scale": "LINEAR"
                        }
                    }
                },
                "width": 24,
                "xPos": 24
            },
            {
                "height": 9,
                "widget": {
                    "scorecard": {
                        "sparkChartView": {
                            "sparkChartType": "SPARK_BAR"
                        },
                        "timeSeriesQuery": {
                            "outputFullDuration": true,
                            "timeSeriesFilter": {
                                "aggregation": {
                                    "alignmentPeriod": "300s",
                                    "crossSeriesReducer": "REDUCE_SUM",
                                    "perSeriesAligner": "ALIGN_DELTA"
                                },
                                "filter": "metric.type=\"logging.googleapis.com/user/ccaas_metadata_chats_escalated\" resource.type=\"logging_bucket\""
                            }
                        }
                    },
                    "title": "Chats Escalated (selected interval)"
                },
                "width": 12,
                "yPos": 16
            },
            {
                "height": 9,
                "widget": {
                    "scorecard": {
                        "sparkChartView": {
                            "sparkChartType": "SPARK_BAR"
                        },
                        "thresholds": [
                            {
                                "color": "RED",
                                "direction": "ABOVE",
                                "value": 10
                            }
                        ],
                        "timeSeriesQuery": {
                            "outputFullDuration": true,
                            "timeSeriesFilter": {
                                "aggregation": {
                                    "alignmentPeriod": "300s",
                                    "crossSeriesReducer": "REDUCE_SUM",
                                    "perSeriesAligner": "ALIGN_SUM"
                                },
                                "filter": "metric.type=\"logging.googleapis.com/user/ccaas_metadata_chats_failed\" resource.type=\"logging_bucket\""
                            }
                        }
                    },
                    "title": "Chats Failed (selected interval)"
                },
                "width": 12,
                "xPos": 12,
                "yPos": 16
            },
            {
                "height": 9,
                "widget": {
                    "scorecard": {
                        "gaugeView": {
                            "upperBound": ${var.escalated_chat_rate_upper_bound}
                        },
                        "timeSeriesQuery": {
                            "timeSeriesFilter": {
                                "aggregation": {
                                    "alignmentPeriod": "300s",
                                    "crossSeriesReducer": "REDUCE_SUM",
                                    "perSeriesAligner": "ALIGN_SUM"
                                },
                                "filter": "metric.type=\"logging.googleapis.com/user/ccaas_metadata_chats_escalated\" resource.type=\"logging_bucket\""
                            }
                        }
                    },
                    "title": "Current Escalated Chat Rate (5 min window)"
                },
                "width": 12,
                "xPos": 24,
                "yPos": 16
            },
            {
                "height": 9,
                "widget": {
                    "scorecard": {
                        "sparkChartView": {
                            "sparkChartType": "SPARK_LINE"
                        },
                        "timeSeriesQuery": {
                            "outputFullDuration": true,
                            "timeSeriesFilter": {
                                "aggregation": {
                                    "alignmentPeriod": "60s",
                                    "crossSeriesReducer": "REDUCE_SUM",
                                    "perSeriesAligner": "ALIGN_SUM"
                                },
                                "filter": "metric.type=\"logging.googleapis.com/user/ccaas_metadata_chats_va_sessions_ended\" metric.label.finish_reason=\"unexpectedly_ended\" resource.type=\"logging_bucket\""
                            }
                        }
                    },
                    "title": "VA Sessions Ended Unexpectedly"
                },
                "width": 12,
                "xPos": 36,
                "yPos": 16
            },
            {
                "height": 16,
                "widget": {
                    "title": "Failed Chats by Fail Reason",
                    "xyChart": {
                        "chartOptions": {
                            "mode": "COLOR"
                        },
                        "dataSets": [
                            {
                                "legendTemplate": "$${metric.labels.fail_reason}",
                                "minAlignmentPeriod": "300s",
                                "plotType": "STACKED_BAR",
                                "targetAxis": "Y1",
                                "timeSeriesQuery": {
                                    "timeSeriesFilter": {
                                        "aggregation": {
                                            "alignmentPeriod": "300s",
                                            "crossSeriesReducer": "REDUCE_SUM",
                                            "groupByFields": [
                                                "metric.label.fail_reason"
                                            ],
                                            "perSeriesAligner": "ALIGN_DELTA"
                                        },
                                        "filter": "metric.type=\"logging.googleapis.com/user/ccaas_metadata_chats_failed\" resource.type=\"logging_bucket\""
                                    }
                                }
                            }
                        ],
                        "yAxis": {
                            "scale": "LINEAR"
                        }
                    }
                },
                "width": 24,
                "yPos": 25
            },
            {
                "height": 16,
                "widget": {
                    "title": "Failed Chats by Chat Type",
                    "xyChart": {
                        "chartOptions": {
                            "mode": "COLOR"
                        },
                        "dataSets": [
                            {
                                "legendTemplate": "$${metric.labels.chat_type}",
                                "minAlignmentPeriod": "300s",
                                "plotType": "STACKED_BAR",
                                "targetAxis": "Y1",
                                "timeSeriesQuery": {
                                    "timeSeriesFilter": {
                                        "aggregation": {
                                            "alignmentPeriod": "300s",
                                            "crossSeriesReducer": "REDUCE_SUM",
                                            "groupByFields": [
                                                "metric.label.chat_type"
                                            ],
                                            "perSeriesAligner": "ALIGN_DELTA"
                                        },
                                        "filter": "metric.type=\"logging.googleapis.com/user/ccaas_metadata_chats_failed\" resource.type=\"logging_bucket\""
                                    }
                                }
                            }
                        ],
                        "yAxis": {
                            "scale": "LINEAR"
                        }
                    }
                },
                "width": 24,
                "xPos": 24,
                "yPos": 25
            },
            {
                "height": 16,
                "widget": {
                    "title": "VA Sessions Ended by Finish Reason",
                    "xyChart": {
                        "chartOptions": {
                            "mode": "COLOR"
                        },
                        "dataSets": [
                            {
                                "legendTemplate": "$${metric.labels.finish_reason}",
                                "minAlignmentPeriod": "300s",
                                "plotType": "STACKED_BAR",
                                "targetAxis": "Y1",
                                "timeSeriesQuery": {
                                    "timeSeriesFilter": {
                                        "aggregation": {
                                            "alignmentPeriod": "300s",
                                            "crossSeriesReducer": "REDUCE_SUM",
                                            "groupByFields": [
                                                "metric.label.finish_reason"
                                            ],
                                            "perSeriesAligner": "ALIGN_DELTA"
                                        },
                                        "filter": "metric.type=\"logging.googleapis.com/user/ccaas_metadata_chats_va_sessions_ended\" resource.type=\"logging_bucket\""
                                    }
                                }
                            }
                        ],
                        "yAxis": {
                            "scale": "LINEAR"
                        }
                    }
                },
                "width": 24,
                "yPos": 41
            },
            {
                "height": 16,
                "widget": {
                    "title": "VA Sessions Ended by Virtual Agent",
                    "xyChart": {
                        "chartOptions": {
                            "mode": "COLOR"
                        },
                        "dataSets": [
                            {
                                "legendTemplate": "$${metric.labels.virtual_agent_name}",
                                "minAlignmentPeriod": "300s",
                                "plotType": "STACKED_BAR",
                                "targetAxis": "Y1",
                                "timeSeriesQuery": {
                                    "timeSeriesFilter": {
                                        "aggregation": {
                                            "alignmentPeriod": "300s",
                                            "crossSeriesReducer": "REDUCE_SUM",
                                            "groupByFields": [
                                                "metric.label.virtual_agent_name"
                                            ],
                                            "perSeriesAligner": "ALIGN_DELTA"
                                        },
                                        "filter": "metric.type=\"logging.googleapis.com/user/ccaas_metadata_chats_va_sessions_ended\" resource.type=\"logging_bucket\""
                                    }
                                }
                            }
                        ],
                        "yAxis": {
                            "scale": "LINEAR"
                        }
                    }
                },
                "width": 24,
                "xPos": 24,
                "yPos": 41
            }
        ]
    }
}
EOF

  project = var.project_id
}
