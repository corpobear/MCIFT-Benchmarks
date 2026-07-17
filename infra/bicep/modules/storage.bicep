param location string
param tags object
param principalId string
param subscriptionId string

var suffix = take(uniqueString(subscriptionId, resourceGroup().id), 10)
var storageName = 'stmcift${suffix}'
var blobContributorRole = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageName
  location: location
  tags: tags
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    supportsHttpsTrafficOnly: true
    minimumTlsVersion: 'TLS1_2'
    publicNetworkAccess: 'Enabled'
    networkAcls: { defaultAction: 'Allow', bypass: 'AzureServices' }
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
  properties: {
    deleteRetentionPolicy: { enabled: true, days: 7 }
    containerDeleteRetentionPolicy: { enabled: true, days: 7 }
  }
}

resource datasets 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'datasets'
  properties: { publicAccess: 'None' }
}
resource runs 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'runs'
  properties: { publicAccess: 'None' }
}
resource approved 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'approved-releases'
  properties: { publicAccess: 'None' }
}

resource datasetAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(datasets.id, principalId, blobContributorRole)
  scope: datasets
  properties: { roleDefinitionId: blobContributorRole, principalId: principalId, principalType: 'ServicePrincipal' }
}
resource runsAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(runs.id, principalId, blobContributorRole)
  scope: runs
  properties: { roleDefinitionId: blobContributorRole, principalId: principalId, principalType: 'ServicePrincipal' }
}

resource lifecycle 'Microsoft.Storage/storageAccounts/managementPolicies@2023-05-01' = {
  parent: storage
  name: 'default'
  properties: {
    policy: {
      rules: [
        {
          name: 'delete-designated-temporary-artifacts'
          enabled: true
          type: 'Lifecycle'
          definition: {
            filters: { blobTypes: ['blockBlob'], prefixMatch: ['runs/temp/', 'runs/failed-temp/'] }
            actions: { baseBlob: { delete: { daysAfterModificationGreaterThan: 30 } } }
          }
        }
      ]
    }
  }
}

output storageAccountName string = storage.name
output storageAccountId string = storage.id
output datasetsContainerId string = datasets.id
output runsContainerId string = runs.id
output approvedContainerId string = approved.id

