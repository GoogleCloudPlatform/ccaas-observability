/**
 * Copyright 2025 Google LLC
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

resource "google_monitoring_dashboard" "errors_dashboard" {
  dashboard_json = <<EOF
{
    "displayName": "CCaaS Errors Dashboard",
    "mosaicLayout": {
        "columns": 48,
        "tiles": [
            {
                "height": 8,
                "width": 16,
                "widget": {
                    "title": "1. Calls Failed",
                    "scorecard": {
                        "sparkChartView": {
                            "sparkChartType": "SPARK_BAR"
                        },
                        "thresholds": [
                            {
                                "color": "RED",
                                "direction": "ABOVE"
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
                                "filter": "metric.type=\"logging.googleapis.com/user/ccaas_calls_failed_v2\" resource.type=\"logging_bucket\""
                            }
                        }
                    }
                }
            },
            {
                "height": 8,
                "width": 16,
                "xPos": 16,
                "widget": {
                    "title": "2. Chats Failed",
                    "scorecard": {
                        "sparkChartView": {
                            "sparkChartType": "SPARK_BAR"
                        },
                        "thresholds": [
                            {
                                "color": "RED",
                                "direction": "ABOVE"
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
                                "filter": "metric.type=\"logging.googleapis.com/user/ccaas_chats_failed\" resource.type=\"logging_bucket\""
                            }
                        }
                    }
                }
            },
            {
                "height": 8,
                "width": 16,
                "xPos": 32,
                "widget": {
                    "title": "3. Virtual Agent Errors",
                    "scorecard": {
                        "sparkChartView": {
                            "sparkChartType": "SPARK_BAR"
                        },
                        "thresholds": [
                            {
                                "color": "RED",
                                "direction": "ABOVE"
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
                                "filter": "metric.type=\"logging.googleapis.com/user/ccaas_streaming_errors_v2\" resource.type=\"logging_bucket\""
                            }
                        }
                    }
                }
            },
            {
                "height": 12,
                "width": 24,
                "yPos": 8,
                "widget": {
                    "title": "4. Call Join Errors Breakdown",
                    "xyChart": {
                        "dataSets": [
                            {
                                "timeSeriesQuery": {
                                    "timeSeriesFilter": {
                                        "filter": "metric.type=\"logging.googleapis.com/user/ccaas_call_participant_join_errors\" resource.type=\"logging_bucket\"",
                                        "aggregation": {
                                            "alignmentPeriod": "300s",
                                            "crossSeriesReducer": "REDUCE_SUM",
                                            "perSeriesAligner": "ALIGN_DELTA"
                                        }
                                    }
                                },
                                "plotType": "LINE",
                                "legendTemplate": "Total",
                                "targetAxis": "Y1"
                            },
                            {
                                "timeSeriesQuery": {
                                    "timeSeriesFilter": {
                                        "filter": "metric.type=\"logging.googleapis.com/user/ccaas_call_human_join_errors\" resource.type=\"logging_bucket\"",
                                        "aggregation": {
                                            "alignmentPeriod": "300s",
                                            "crossSeriesReducer": "REDUCE_SUM",
                                            "perSeriesAligner": "ALIGN_DELTA"
                                        }
                                    }
                                },
                                "plotType": "LINE",
                                "legendTemplate": "Human",
                                "targetAxis": "Y1"
                            },
                            {
                                "timeSeriesQuery": {
                                    "timeSeriesFilter": {
                                        "filter": "metric.type=\"logging.googleapis.com/user/ccaas_call_virtual_join_errors\" resource.type=\"logging_bucket\"",
                                        "aggregation": {
                                            "alignmentPeriod": "300s",
                                            "crossSeriesReducer": "REDUCE_SUM",
                                            "perSeriesAligner": "ALIGN_DELTA"
                                        }
                                    }
                                },
                                "plotType": "LINE",
                                "legendTemplate": "Virtual Agent",
                                "targetAxis": "Y1"
                            }
                        ],
                        "yAxis": {
                            "scale": "LINEAR"
                        }
                    }
                }
            },
            {
                "height": 12,
                "width": 24,
                "xPos": 24,
                "yPos": 8,
                "widget": {
                    "title": "5. Chat Join Errors Breakdown",
                    "xyChart": {
                        "dataSets": [
                            {
                                "timeSeriesQuery": {
                                    "timeSeriesFilter": {
                                        "filter": "metric.type=\"logging.googleapis.com/user/ccaas_chat_participant_join_errors\" resource.type=\"logging_bucket\"",
                                        "aggregation": {
                                            "alignmentPeriod": "300s",
                                            "crossSeriesReducer": "REDUCE_SUM",
                                            "perSeriesAligner": "ALIGN_DELTA"
                                        }
                                    }
                                },
                                "plotType": "LINE",
                                "legendTemplate": "Total",
                                "targetAxis": "Y1"
                            },
                            {
                                "timeSeriesQuery": {
                                    "timeSeriesFilter": {
                                        "filter": "metric.type=\"logging.googleapis.com/user/ccaas_chat_human_join_errors\" resource.type=\"logging_bucket\"",
                                        "aggregation": {
                                            "alignmentPeriod": "300s",
                                            "crossSeriesReducer": "REDUCE_SUM",
                                            "perSeriesAligner": "ALIGN_DELTA"
                                        }
                                    }
                                },
                                "plotType": "LINE",
                                "legendTemplate": "Human",
                                "targetAxis": "Y1"
                            },
                            {
                                "timeSeriesQuery": {
                                    "timeSeriesFilter": {
                                        "filter": "metric.type=\"logging.googleapis.com/user/ccaas_chat_virtual_join_errors\" resource.type=\"logging_bucket\"",
                                        "aggregation": {
                                            "alignmentPeriod": "300s",
                                            "crossSeriesReducer": "REDUCE_SUM",
                                            "perSeriesAligner": "ALIGN_DELTA"
                                        }
                                    }
                                },
                                "plotType": "LINE",
                                "legendTemplate": "Virtual Agent",
                                "targetAxis": "Y1"
                            }
                        ],
                        "yAxis": {
                            "scale": "LINEAR"
                        }
                    }
                }
            },
            {
                "height": 16,
                "width": 24,
                "yPos": 20,
                "widget": {
                    "title": "6. Call Failure Ratio (5m) %",
                    "xyChart": {
                        "chartOptions": {
                            "mode": "COLOR"
                        },
                        "dataSets": [
                            {
                                "plotType": "LINE",
                                "targetAxis": "Y1",
                                "timeSeriesQuery": {
                                    "timeSeriesQueryLanguage": "{\n  fetch logging_bucket | metric 'logging.googleapis.com/user/ccaas_calls_failed_v2' | align delta(300s) | group_by [], [v: sum(val())];\n  fetch logging_bucket | metric 'logging.googleapis.com/user/ccaas_calls_established_v2' | align delta(300s) | group_by [], [v: sum(val())]\n}\n| ratio | mul(100)"
                                }
                            }
                        ],
                        "yAxis": {
                            "scale": "LINEAR"
                        }
                    }
                }
            },
            {
                "height": 16,
                "width": 24,
                "xPos": 24,
                "yPos": 20,
                "widget": {
                    "title": "7. Call Failure Ratio (60m) %",
                    "xyChart": {
                        "chartOptions": {
                            "mode": "COLOR"
                        },
                        "dataSets": [
                            {
                                "plotType": "LINE",
                                "targetAxis": "Y1",
                                "timeSeriesQuery": {
                                    "timeSeriesQueryLanguage": "{\n  fetch logging_bucket | metric 'logging.googleapis.com/user/ccaas_calls_failed_v2' | align delta(3600s) | group_by [], [v: sum(val())];\n  fetch logging_bucket | metric 'logging.googleapis.com/user/ccaas_calls_established_v2' | align delta(3600s) | group_by [], [v: sum(val())]\n}\n| ratio | mul(100)"
                                }
                            }
                        ],
                        "yAxis": {
                            "scale": "LINEAR"
                        }
                    }
                }
            },
            {
                "height": 16,
                "width": 24,
                "yPos": 36,
                "widget": {
                    "title": "8. Chat Failure Ratio (5m) %",
                    "xyChart": {
                        "chartOptions": {
                            "mode": "COLOR"
                        },
                        "dataSets": [
                            {
                                "plotType": "LINE",
                                "targetAxis": "Y1",
                                "timeSeriesQuery": {
                                    "timeSeriesQueryLanguage": "{\n  fetch logging_bucket | metric 'logging.googleapis.com/user/ccaas_chats_failed' | align delta(300s) | group_by [], [v: sum(val())];\n  fetch logging_bucket | metric 'logging.googleapis.com/user/ccaas_chats_successful' | align delta(300s) | group_by [], [v: sum(val())]\n}\n| ratio | mul(100)"
                                }
                            }
                        ],
                        "yAxis": {
                            "scale": "LINEAR"
                        }
                    }
                }
            },
            {
                "height": 16,
                "width": 24,
                "xPos": 24,
                "yPos": 36,
                "widget": {
                    "title": "9. Chat Failure Ratio (60m) %",
                    "xyChart": {
                        "chartOptions": {
                            "mode": "COLOR"
                        },
                        "dataSets": [
                            {
                                "plotType": "LINE",
                                "targetAxis": "Y1",
                                "timeSeriesQuery": {
                                    "timeSeriesQueryLanguage": "{\n  fetch logging_bucket | metric 'logging.googleapis.com/user/ccaas_chats_failed' | align delta(3600s) | group_by [], [v: sum(val())];\n  fetch logging_bucket | metric 'logging.googleapis.com/user/ccaas_chats_successful' | align delta(3600s) | group_by [], [v: sum(val())]\n}\n| ratio | mul(100)"
                                }
                            }
                        ],
                        "yAxis": {
                            "scale": "LINEAR"
                        }
                    }
                }
            },
            {
                "height": 16,
                "width": 24,
                "yPos": 52,
                "widget": {
                    "title": "10. Virtual Agent Error Ratio (5m) %",
                    "xyChart": {
                        "chartOptions": {
                            "mode": "COLOR"
                        },
                        "dataSets": [
                            {
                                "plotType": "LINE",
                                "targetAxis": "Y1",
                                "timeSeriesQuery": {
                                    "timeSeriesQueryLanguage": "{\n  fetch logging_bucket | metric 'logging.googleapis.com/user/ccaas_streaming_errors_v2' | align delta(5m) | group_by [], [v: sum(val())];\n  {\n    fetch logging_bucket | metric 'logging.googleapis.com/user/ccaas_calls_failed_v2' | align delta(5m) | group_by [], [v: sum(val())];\n    fetch logging_bucket | metric 'logging.googleapis.com/user/ccaas_calls_established_v2' | align delta(5m) | group_by [], [v: sum(val())];\n    fetch logging_bucket | metric 'logging.googleapis.com/user/ccaas_chats_failed' | align delta(5m) | group_by [], [v: sum(val())];\n    fetch logging_bucket | metric 'logging.googleapis.com/user/ccaas_chats_successful' | align delta(5m) | group_by [], [v: sum(val())]\n  } | union | group_by [], [v: sum(v)]\n}\n| ratio | mul(100)"
                                }
                            }
                        ],
                        "yAxis": {
                            "scale": "LINEAR"
                        }
                    }
                }
            },
            {
                "height": 16,
                "width": 24,
                "xPos": 24,
                "yPos": 52,
                "widget": {
                    "title": "11. Virtual Agent Error Ratio (60m) %",
                    "xyChart": {
                        "chartOptions": {
                            "mode": "COLOR"
                        },
                        "dataSets": [
                            {
                                "plotType": "LINE",
                                "targetAxis": "Y1",
                                "timeSeriesQuery": {
                                    "timeSeriesQueryLanguage": "{\n  fetch logging_bucket | metric 'logging.googleapis.com/user/ccaas_streaming_errors_v2' | align delta(60m) | group_by [], [v: sum(val())];\n  {\n    fetch logging_bucket | metric 'logging.googleapis.com/user/ccaas_calls_failed_v2' | align delta(60m) | group_by [], [v: sum(val())];\n    fetch logging_bucket | metric 'logging.googleapis.com/user/ccaas_calls_established_v2' | align delta(60m) | group_by [], [v: sum(val())];\n    fetch logging_bucket | metric 'logging.googleapis.com/user/ccaas_chats_failed' | align delta(60m) | group_by [], [v: sum(val())];\n    fetch logging_bucket | metric 'logging.googleapis.com/user/ccaas_chats_successful' | align delta(60m) | group_by [], [v: sum(val())]\n  } | union | group_by [], [v: sum(v)]\n}\n| ratio | mul(100)"
                                }
                            }
                        ],
                        "yAxis": {
                            "scale": "LINEAR"
                        }
                    }
                }
            },
            {
                "height": 16,
                "width": 48,
                "yPos": 68,
                "widget": {
                    "title": "12. Virtual Agent Errors by Type",
                    "xyChart": {
                        "dataSets": [
                            {
                                "timeSeriesQuery": {
                                    "timeSeriesFilter": {
                                        "filter": "metric.type=\"logging.googleapis.com/user/ccaas_streaming_errors_v2\" resource.type=\"logging_bucket\"",
                                        "aggregation": {
                                            "alignmentPeriod": "300s",
                                            "crossSeriesReducer": "REDUCE_SUM",
                                            "perSeriesAligner": "ALIGN_DELTA",
                                            "groupByFields": [
                                                "metric.label.error_type"
                                            ]
                                        }
                                    }
                                },
                                "plotType": "LINE",
                                "targetAxis": "Y1"
                            }
                        ],
                        "yAxis": {
                            "scale": "LINEAR"
                        }
                    }
                }
            },
            {
                "height": 16,
                "width": 24,
                "yPos": 84,
                "widget": {
                    "title": "13. Call Virtual Join Errors by Agent ID",
                    "xyChart": {
                        "dataSets": [
                            {
                                "timeSeriesQuery": {
                                    "timeSeriesFilter": {
                                        "filter": "metric.type=\"logging.googleapis.com/user/ccaas_call_virtual_join_errors_v2\" resource.type=\"logging_bucket\"",
                                        "aggregation": {
                                            "alignmentPeriod": "300s",
                                            "crossSeriesReducer": "REDUCE_SUM",
                                            "perSeriesAligner": "ALIGN_DELTA",
                                            "groupByFields": [
                                                "metric.label.virtual_agent_id"
                                            ]
                                        }
                                    }
                                },
                                "plotType": "LINE",
                                "targetAxis": "Y1"
                            }
                        ],
                        "yAxis": {
                            "scale": "LINEAR"
                        }
                    }
                }
            },
            {
                "height": 16,
                "width": 24,
                "xPos": 24,
                "yPos": 84,
                "widget": {
                    "title": "14. Chat Virtual Join Errors by Agent ID",
                    "xyChart": {
                        "dataSets": [
                            {
                                "timeSeriesQuery": {
                                    "timeSeriesFilter": {
                                        "filter": "metric.type=\"logging.googleapis.com/user/ccaas_chat_virtual_join_errors_v2\" resource.type=\"logging_bucket\"",
                                        "aggregation": {
                                            "alignmentPeriod": "300s",
                                            "crossSeriesReducer": "REDUCE_SUM",
                                            "perSeriesAligner": "ALIGN_DELTA",
                                            "groupByFields": [
                                                "metric.label.virtual_agent_id"
                                            ]
                                        }
                                    }
                                },
                                "plotType": "LINE",
                                "targetAxis": "Y1"
                            }
                        ],
                        "yAxis": {
                            "scale": "LINEAR"
                        }
                    }
                }
            },
            {
                "height": 16,
                "width": 48,
                "yPos": 100,
                "widget": {
                    "title": "15. Global Failure Ratio Delta (1d Platform Trend) %",
                    "xyChart": {
                        "chartOptions": {
                            "mode": "COLOR"
                        },
                        "dataSets": [
                            {
                                "plotType": "LINE",
                                "targetAxis": "Y1",
                                "timeSeriesQuery": {
                                    "prometheusQuery": "(((sum(rate(logging_googleapis_com:user_ccaas_calls_failed_v2[1h])) or on() vector(0)) / ((sum(rate(logging_googleapis_com:user_ccaas_calls_established_v2[1h])) + sum(rate(logging_googleapis_com:user_ccaas_calls_failed_v2[1h]))) or on() vector(0))) - ((sum(rate(logging_googleapis_com:user_ccaas_calls_failed_v2[1h] offset 1d)) or on() vector(0)) / ((sum(rate(logging_googleapis_com:user_ccaas_calls_established_v2[1h] offset 1d)) + sum(rate(logging_googleapis_com:user_ccaas_calls_failed_v2[1h] offset 1d))) or on() vector(0)))) * 100"
                                }
                            }
                        ],
                        "yAxis": {
                            "scale": "LINEAR"
                        }
                    }
                }
            },
            {
                "height": 24,
                "width": 48,
                "yPos": 116,
                "widget": {
                    "title": "Dashboard Documentation",
                    "text": {
                        "content": "### CCaaS Errors Dashboard Reference\n\n1. **Calls Failed**: Total absolute count of all calls that ended in a failed state (regardless of point of failure).\n2. **Chats Failed**: Total absolute count of all chats that ended in a failed state.\n3. **Virtual Agent Errors**: Absolute count of errors within the Voice Platform and Streaming pipeline (e.g., Speech-to-Text failures, missing Agent configuration).\n4. **Call Join Errors Breakdown**: Distribution of call failures that occurred *before* connection, categorized by who failed to join (Human, Virtual Agent, or Total).\n5. **Chat Join Errors Breakdown**: Distribution of chat failures that occurred *before* connection, categorized by who failed to join.\n6. **Call Failure Ratio (5m)**: Percentage of calls that fail out of the total initiated calls, calculated over a rolling 5-minute window.\n7. **Call Failure Ratio (60m)**: Percentage of calls that fail out of the total initiated calls, calculated over a rolling 60-minute window.\n8. **Chat Failure Ratio (5m)**: Percentage of chats that fail out of the total initiated chats, calculated over a rolling 5-minute window.\n9. **Chat Failure Ratio (60m)**: Percentage of chats that fail out of the total initiated chats, calculated over a rolling 60-minute window.\n10. **Virtual Agent Error Ratio (5m)**: Percentage of audio/streaming failures relative to the total combined volume of all calls and chats, calculated over a 5-minute window.\n11. **Virtual Agent Error Ratio (60m)**: Percentage of audio/streaming failures relative to the total combined volume of all calls and chats, calculated over a 60-minute window.\n12. **Virtual Agent Errors by Type**: A breakdown of the raw streaming/voice platform errors grouped by their gRPC error code (e.g., INVALID_ARGUMENT, INTERNAL).\n13. **Call Virtual Join Errors by Agent ID**: Absolute count of call join errors grouped by the specific virtual agent ID.\n14. **Chat Virtual Join Errors by Agent ID**: Absolute count of chat join errors grouped by the specific virtual agent ID.\n15. **Global Failure Ratio Delta (1d Platform Trend)**: Compares the platform's current 1-hour rolling failure ratio against the same ratio from exactly 24 hours ago. Values above 0% indicate the platform is performing worse today than yesterday; values below 0% indicate improved stability.",
                        "format": "MARKDOWN",
                        "style": {}
                    }
                }
            }
        ]
    }
}
EOF
}
