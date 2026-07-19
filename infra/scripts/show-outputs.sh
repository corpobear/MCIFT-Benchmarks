#!/usr/bin/env bash
set -euo pipefail
az deployment sub show --name mcift-benchmark-prepare --query properties.outputs --output json
az containerapp job execution list --resource-group rg-mcift-benchmarks-weu --name caj-mcift-ims --query 'length(@)' -o tsv
az ml compute show --resource-group rg-mcift-benchmarks-weu --workspace-name mlw-mcift-benchmarks --name cpu-mcift-exathlon --query '{state:state,min:scaleSettings.minNodeCount,max:scaleSettings.maxNodeCount}' -o json
az ml online-endpoint list --resource-group rg-mcift-benchmarks-weu --workspace-name mlw-mcift-benchmarks --query 'length(@)' -o tsv

