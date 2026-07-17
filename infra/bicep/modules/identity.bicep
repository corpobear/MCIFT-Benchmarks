param location string
param tags object

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-mcift-benchmarks'
  location: location
  tags: tags
}

output name string = identity.name
output identityId string = identity.id
output principalId string = identity.properties.principalId
output clientId string = identity.properties.clientId

