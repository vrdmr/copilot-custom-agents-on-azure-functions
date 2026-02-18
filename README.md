# Cloud Copilot Runtime Demo

This project demonstrates a vision for deploying GitHub Copilot agents to a cloud agent runtime. The core idea is simple: **your agent source code should be portable** — no SDKs, no cloud-specific frameworks, just pure agent definitions that run anywhere. The same agent artifacts: AGENTS.md, skills, and MCP servers runs locally in VS Code Copilot Chat and remotely in a cloud runtime with zero code changes.

The workflow is simple:

1. Define and test your agent in VS Code in a standard Copilot project structure
2. Deploy the same project to the cloud with `azd up`
3. Consume your cloud-hosted agent via HTTP endpoints or as an MCP server (coming soon)

## Project Structure

```
src/                    # Your agent - pure Copilot project, no cloud knowledge
├── AGENTS.md          # Agent instructions and behavior
├── .github/skills/    # Agent skills
└── .vscode/mcp.json   # MCP server configurations
```

The `src` folder contains **only** your agent definition. There's no Copilot SDK, no Azure Functions code, no cloud infrastructure concerns. It's just a standard Copilot project.

## Running Locally

1. Open the `src` folder in VS Code
2. Enable the experimental setting: `chat.useAgentSkills`
3. Enable built-in tools in Copilot Chat
4. Start chatting with your agent in VS Code Copilot Chat

That's it. Your agent's instructions from `AGENTS.md`, skills from `.github/skills`, and MCP servers from `.vscode/mcp.json` are all automatically loaded.

## Running in the Cloud

### Prerequisites: Create a GitHub Personal Access Token

The cloud runtime requires a GitHub token with Copilot permissions:

1. Go to https://github.com/settings/personal-access-tokens/new
2. Under **Permissions**, click **+ Add permissions**
3. In the **Select account permissions** dropdown, check **Copilot Requests** (Read-only)
4. Click **Generate token** and save it securely

### Deploy with Azure Developer CLI

```bash
azd up
```

During deployment, you'll be prompted for:

| Prompt | Description |
|--------|-------------|
| **GitHub Token** | Your GitHub PAT with Copilot Requests permission (required — see above) |
| **Azure Location** | Azure region for deployment |
| **Model Selection** | Which model to use (see below) |
| **VNet Enabled** | Whether to deploy with VNet integration |

#### Model Selection

You can choose from two categories of models:

- **GitHub models** (`github:` prefix) — Use the GitHub Copilot model API. No additional Azure infrastructure is deployed. Examples: `github:claude-sonnet-4.6`, `github:claude-opus-4.6`, `github:gpt-5.2`
- **Microsoft Foundry models** (`foundry:` prefix) — Deploys a Microsoft Foundry account and model in your subscription. Examples: `foundry:gpt-4.1-mini`, `foundry:claude-opus-4-6`, `foundry:o4-mini`

To change the model after initial deployment:

```bash
azd env set MODEL_SELECTION "github:gpt-5.2"
azd up
```

### Session Persistence

When running in Azure, agent sessions are automatically persisted to an Azure Files share mounted into the function app. This means conversation state survives across function app restarts and is shared across all instances, enabling multi-turn conversations with session resumption.

Locally, sessions are stored in `~/.copilot/session-state/`.

## Using the API

The agent exposes a single endpoint: `POST /agent/chat`

### Basic Request

```bash
curl -X POST "https://<your-app>.azurewebsites.net/agent/chat?code=<function-key>" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Who is playing in the Super Bowl this year?"}'
```

### Response

```json
{
  "session_id": "abc123-def456-...",
  "response": "The agent's final response text",
  "response_intermediate": "Any intermediate responses",
  "tool_calls": ["list of tools invoked during the response"]
}
```

The response always includes a `session_id` (also returned in the `x-ms-session-id` response header). Use this ID to continue the conversation.

### Multi-Turn Conversations

To resume an existing session, pass the session ID in the `x-ms-session-id` request header:

```bash# Follow-up — resumes the same session with full conversation history
curl -X POST "https://<your-app>.azurewebsites.net/agent/chat?code=<function-key>" \
  -H "Content-Type: application/json" \
  -H "x-ms-session-id: abc123-def456-..." \
  -d '{"prompt": "What were we just discussing?"}'
```

If you omit `x-ms-session-id`, a new session is created automatically and its ID is returned in the response. See `test/test.cloud.http` for more examples.

The Azure Developer CLI deploys your agent to Azure Functions. Behind the scenes, your Copilot project is automatically transformed into a cloud-hosted agent endpoint — but you don't need to know or care about those details.

## Why This Matters

This demo illustrates a future where:

- **Agent authors focus on agent logic**, not infrastructure
- **The same agent runs locally and in the cloud** with no modifications
- **Cloud platforms natively understand Copilot projects** and can run them directly

## Try It

1. Clone this repo
2. Explore the `src` folder to see a minimal agent definition
4. Run `azd up` to deploy to the cloud
5. Test the cloud endpoint at `/agent/chat` (see `test/test.cloud.http` for examples)
