param location string
param tags object
param identityId string
param storageAccountId string
param applicationInsightsId string
param benchmarkImage string
param deployCompute bool

resource vault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: 'kv-mcift-${take(uniqueString(resourceGroup().id), 10)}'
  location: location
  tags: tags
  properties: {
    tenantId: subscription().tenantId
    sku: { family: 'A', name: 'standard' }
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    publicNetworkAccess: 'Enabled'
    accessPolicies: []
  }
}

resource workspace 'Microsoft.MachineLearningServices/workspaces@2024-04-01' = {
  name: 'mlw-mcift-benchmarks'
  location: location
  tags: tags
  identity: { type: 'SystemAssigned,UserAssigned', userAssignedIdentities: { '${identityId}': {} } }
  properties: {
    friendlyName: 'MCIFT public benchmarks'
    storageAccount: storageAccountId
    keyVault: vault.id
    applicationInsights: applicationInsightsId
    publicNetworkAccess: 'Enabled'
    hbiWorkspace: false
  }
}

resource compute 'Microsoft.MachineLearningServices/workspaces/computes@2024-04-01' = if (deployCompute) {
  parent: workspace
  name: 'cpu-mcift-exathlon'
  location: location
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${identityId}': {} } }
  properties: {
    computeType: 'AmlCompute'
    disableLocalAuth: true
    properties: {
      vmSize: 'Standard_D8as_v5'
      vmPriority: 'LowPriority'
      scaleSettings: { minNodeCount: 0, maxNodeCount: 1, nodeIdleTimeBeforeScaleDown: 'PT120S' }
    }
  }
}

resource environmentVersion 'Microsoft.MachineLearningServices/workspaces/environments/versions@2024-04-01' = {
  name: '${workspace.name}/mcift-benchmarks/1'
  properties: {
    image: benchmarkImage
    isAnonymous: false
  }
}

output workspaceName string = workspace.name
output computeName string = 'cpu-mcift-exathlon'
output environmentVersion string = environmentVersion.name
