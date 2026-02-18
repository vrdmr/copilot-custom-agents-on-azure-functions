@description('Name of the Microsoft Foundry account')
param aiFoundryName string

@description('Name of the Microsoft Foundry project')
param aiProjectName string = '${aiFoundryName}-proj'

@description('Location for the resources. Model catalog is validated against this region.')
param location string = 'eastus2'

@description('Tags to apply to the resources')
param tags object = {}

@description('Model to deploy (GlobalStandard SKU). Must exist in the modelCatalog variable below.')
param model string = 'gpt-4.1-mini'

// Model catalog — maps model name to its format and default version
var modelCatalog = {
  'gpt-4.1': { format: 'OpenAI', version: '2025-04-14' }
  'gpt-4.1-mini': { format: 'OpenAI', version: '2025-04-14' }
  'gpt-4.1-nano': { format: 'OpenAI', version: '2025-04-14' }
  'gpt-4o': { format: 'OpenAI', version: '2024-11-20' }
  'gpt-4o-mini': { format: 'OpenAI', version: '2024-07-18' }
  'gpt-5': { format: 'OpenAI', version: '2025-08-07' }
  'gpt-5-chat': { format: 'OpenAI', version: '2025-10-03' }
  'gpt-5-codex': { format: 'OpenAI', version: '2025-09-15' }
  'gpt-5-mini': { format: 'OpenAI', version: '2025-08-07' }
  'gpt-5-nano': { format: 'OpenAI', version: '2025-08-07' }
  'gpt-5-pro': { format: 'OpenAI', version: '2025-10-06' }
  'gpt-5.1': { format: 'OpenAI', version: '2025-11-13' }
  'gpt-5.1-chat': { format: 'OpenAI', version: '2025-11-13' }
  'gpt-5.1-codex': { format: 'OpenAI', version: '2025-11-13' }
  'gpt-5.1-codex-max': { format: 'OpenAI', version: '2025-12-04' }
  'gpt-5.1-codex-mini': { format: 'OpenAI', version: '2025-11-13' }
  'gpt-5.2': { format: 'OpenAI', version: '2025-12-11' }
  'gpt-5.2-chat': { format: 'OpenAI', version: '2025-12-11' }
  'gpt-5.2-codex': { format: 'OpenAI', version: '2026-01-14' }
  'codex-mini': { format: 'OpenAI', version: '2025-05-16' }
  o1: { format: 'OpenAI', version: '2024-12-17' }
  'o3-mini': { format: 'OpenAI', version: '2025-01-31' }
  'o4-mini': { format: 'OpenAI', version: '2025-04-16' }
  'model-router': { format: 'OpenAI', version: '2025-11-18' }
  'text-embedding-3-small': { format: 'OpenAI', version: '1' }
  'text-embedding-3-large': { format: 'OpenAI', version: '1' }
  'DeepSeek-R1': { format: 'DeepSeek', version: '1' }
  'DeepSeek-V3': { format: 'DeepSeek', version: '1' }
  'Llama-4-Maverick-17B-128E-Instruct-FP8': { format: 'Meta', version: '1' }
  'Llama-4-Scout-17B-16E-Instruct': { format: 'Meta', version: '1' }
  'Llama-3.3-70B-Instruct': { format: 'Meta', version: '5' }
  'MAI-DS-R1': { format: 'Microsoft', version: '1' }
  'Phi-4': { format: 'Microsoft', version: '7' }
  'Phi-4-mini-instruct': { format: 'Microsoft', version: '1' }
  'Phi-4-reasoning': { format: 'Microsoft', version: '1' }
  'Phi-4-multimodal-instruct': { format: 'Microsoft', version: '1' }
  'Mistral-Large-3': { format: 'Mistral AI', version: '1' }
  'Mistral-Nemo': { format: 'Mistral AI', version: '1' }
  'Codestral-2501': { format: 'Mistral AI', version: '2' }
  'cohere-command-a': { format: 'Cohere', version: '1' }
  'Cohere-command-r-plus-08-2024': { format: 'Cohere', version: '1' }
  'claude-sonnet-4-5': { format: 'Anthropic', version: '20250929' }
  'claude-opus-4-6': { format: 'Anthropic', version: '1' }
  'claude-haiku-4-5': { format: 'Anthropic', version: '20251001' }
  'grok-4-fast-reasoning': { format: 'xAI', version: '1' }
  'grok-4-fast-non-reasoning': { format: 'xAI', version: '1' }
  'Kimi-K2-Thinking': { format: 'MoonshotAI', version: '1' }
  'qwen3-32b': { format: 'Alibaba', version: '1' }
}

var modelName = model
var modelFormat = modelCatalog[model].format
var modelVersion = modelCatalog[model].version

@description('SKU name for the model deployment')
param modelSkuName string = 'GlobalStandard'

@description('SKU capacity for the model deployment')
param modelSkuCapacity int = 200

/*
  A Microsoft Foundry resource is a variant of a CognitiveServices/account resource type.
*/
resource aiFoundry 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: aiFoundryName
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  sku: {
    name: 'S0'
  }
  kind: 'AIServices'
  properties: {
    allowProjectManagement: true
    customSubDomainName: aiFoundryName
    disableLocalAuth: false
    publicNetworkAccess: 'Enabled'
  }
}

/*
  Developer APIs are exposed via a project, which groups in- and outputs that
  relate to one use case, including files.
*/
resource aiProject 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  name: aiProjectName
  parent: aiFoundry
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {}
}

/*
  Deploy a model to use in playground, agents and other tools.
*/
resource modelDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: aiFoundry
  name: modelName
  dependsOn: [aiProject]
  sku: {
    capacity: modelSkuCapacity
    name: modelSkuName
  }
  properties: {
    model: {
      name: modelName
      format: modelFormat
      version: modelVersion
    }
  }
}

output aiFoundryName string = aiFoundry.name
output aiFoundryEndpoint string = aiFoundry.properties.endpoint
output aiFoundryOpenAIEndpoint string = 'https://${aiFoundryName}.openai.azure.com/openai/v1/'
output aiProjectName string = aiProject.name
output modelDeploymentName string = modelDeployment.name

#disable-next-line outputs-should-not-contain-secrets
output aiFoundryApiKey string = aiFoundry.listKeys().key1
