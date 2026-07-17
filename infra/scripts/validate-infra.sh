#!/usr/bin/env bash
set -euo pipefail
az bicep build --file infra/bicep/main.bicep
az deployment sub validate --location westeurope --template-file infra/bicep/main.bicep --parameters infra/bicep/parameters/research.bicepparam

