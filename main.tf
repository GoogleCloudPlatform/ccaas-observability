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

module "ccaas_calls_dashboard" {
  source                            = "./modules/calls_dashboard"
  project_id                        = var.project_id
  established_call_rate_upper_bound = var.established_call_rate_upper_bound
}

module "ccaas_chats_dashboard" {
  source                          = "./modules/chats_dashboard"
  project_id                      = var.project_id
  escalated_chat_rate_upper_bound = var.escalated_chat_rate_upper_bound
}

module "df_dashboard" {
  source     = "./modules/df_dashboard"
  project_id = var.project_id
}

module "ccaas_errors_dashboard" {
  source     = "./modules/errors_dashboard"
  project_id = var.project_id
}

module "ccaas_log_analytics_dashboard" {
  source     = "./modules/analytics_dashboard"
  project_id = var.project_id
}

module "ccaas_platform_dashboard" {
  source     = "./modules/platform_dashboard"
  project_id = var.project_id
}

module "metadata_logger" {
  count                   = var.enable_metadata_logger ? 1 : 0
  source                  = "./modules/metadata_logger"
  storage_project_id      = var.metadata_logger.storage_project_id
  region                  = var.metadata_logger.region
  gcs_path_configs        = var.metadata_logger.path_configs
  image_url               = var.metadata_logger.image_url
  grant_project_iam_roles = var.metadata_logger.grant_project_iam_roles
  enable_apis             = var.metadata_logger.enable_apis
  custom_log_name         = var.metadata_logger.custom_log_name
  state_bucket            = var.metadata_logger.state_bucket
}


