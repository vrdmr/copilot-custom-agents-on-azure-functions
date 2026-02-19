# Markdown-Based Agents on Azure Functions (Experimental)

> **⚠️ This is an experimental feature.** The agent runtime, deployment model, and APIs described here are under active development and subject to change.

Today, you can build custom agents with GitHub Copilot right in VS Code. You define your agent's personality and behavior in a markdown file (`AGENTS.md`), add skills as knowledge files, configure MCP servers for live data and actions, and even write custom tools as plain Python functions. All of that just works in Copilot Chat — locally, on your machine.

**Hosting your agent in the cloud**

Azure Functions is a serverless compute platform that already supports runtimes like JavaScript, Python, and .NET. An agent project with `AGENTS.md`, skills, and MCP servers is just another workload. This experiment adds a new runtime to Azure Functions that natively understands and runs markdown-based agent projects.

Development workflow:

1. Define and test your agent in VS Code as a standard Copilot project
2. Deploy the same project to Azure Functions with `azd up`
3. Your agent is now a cloud-hosted HTTP API — no rewrites needed

This repo includes a sample **Microsoft expert agent** that helps developers and architects look up Azure pricing, estimate costs, and find answers in official Microsoft Learn documentation.

## Project Structure

```
src/                       # Your agent — a pure Copilot project, no cloud knowledge
├── AGENTS.md             # Agent instructions and behavior (+ optional frontmatter)
├── .github/skills/
│   └── azure-pricing/    # Skill: fetch real-time Azure retail pricing
│       └── SKILL.md
├── .vscode/mcp.json      # MCP servers (Microsoft Learn)
└── tools/
    └── cost_estimator.py # Tool: estimate monthly/annual costs from a unit price
```

The `src` folder contains **only** your agent definition — no Copilot SDK, no Azure Functions code, no cloud infrastructure concerns. It's just a standard markdown-based agent project. The agent format is the programming model.

`AGENTS.md` supports optional YAML frontmatter. The runtime strips frontmatter before passing instructions to Copilot, and uses frontmatter metadata for runtime features (for example, timer triggers).

## Running Locally in VS Code

1. Open the `src` folder in VS Code
2. Enable the experimental setting: `chat.useAgentSkills`
3. Enable built-in tools in Copilot Chat
4. Start chatting with your agent in Copilot Chat

Your agent's instructions from `AGENTS.md`, skills from `.github/skills/`, and MCP servers from `.vscode/mcp.json` are all automatically loaded.

## Deploying to Azure Functions

### Prerequisites: Create a GitHub Personal Access Token

The cloud runtime requires a GitHub token with Copilot permissions. GitHub Copilot requires authentication to persist and resume sessions (even though sessions are stored locally). If you choose a GitHub model (see [Model Selection](#model-selection)), the token is also used to access the model.

1. Go to https://github.com/settings/personal-access-tokens/new
2. Under **Permissions**, click **+ Add permissions**
3. In the **Select account permissions** dropdown, check **Copilot Requests** (Read-only)
4. Click **Generate token** and save it securely

### Deploy with Azure Developer CLI

From the terminal, run the following command:

```bash
azd up
```

Within minutes, you have a fully deployed agent behind an HTTP API. The same source code that runs locally in Copilot Chat now runs remotely on Azure Functions.

During deployment, you'll be prompted for:

| Prompt | Description |
|--------|-------------|
| **GitHub Token** | Your GitHub PAT with Copilot Requests permission (required — used for session persistence and GitHub model access) |
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

## Timer Triggers from `AGENTS.md` Frontmatter

You can define scheduled agent runs directly in `src/AGENTS.md` frontmatter using a `functions` array.

```yaml
---
functions:
  - name: timerAgent
    trigger: timer
    schedule: "0 */2 * * * *"
    prompt: "What's the price of a Standard_D4s_v5 VM in East US?"
    logger: true
---
```

Current behavior:

- Only `trigger: timer` is supported right now. Other trigger types are explicitly rejected at startup.
- `functions` section is optional.
- `schedule` and `prompt` are required for timer entries.
- `name` is optional (a safe unique name is generated if omitted).
- `logger` is optional and defaults to `true`.

When `logger: true`, the timer logs full agent output via `logging.info`, including:

- `session_id`
- final `response`
- `response_intermediate`
- `tool_calls`

Timer functions are registered at startup from frontmatter and run in the same runtime as `/agent/chat`.

## Using the Chat UI (Root Route)

After deployment, open your function app root URL:

```text
https://<your-app>.azurewebsites.net/
```

The root route serves a built-in single-page chat UI.

At first load, enter:

- Base URL (typically your function app URL)
- Chat function key

These values are stored in browser local storage. You can reopen/edit them later via the gear icon.

You can also prefill both values via URL hash:

```text
https://<your-app>.azurewebsites.net/#baseUrl=https%3A%2F%2F<your-app>.azurewebsites.net&key=<url-encoded-key>
```

On load, the page reads and stores these values, then removes the hash from the address bar.

## Using the API

Once deployed, your agent is available as an HTTP API. It exposes a single endpoint: `POST /agent/chat`

### Basic Request

```bash
curl -X POST "https://<your-app>.azurewebsites.net/agent/chat?code=<function-key>" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What is the price of a Standard_D4s_v5 VM in East US?"}'
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

```bash
# Follow-up — resumes the same session with full conversation history
curl -X POST "https://<your-app>.azurewebsites.net/agent/chat?code=<function-key>" \
  -H "Content-Type: application/json" \
  -H "x-ms-session-id: abc123-def456-..." \
  -d '{"prompt": "If I run that VM 24/7 for a month, what would it cost?"}'
```

If you omit `x-ms-session-id`, a new session is created automatically and its ID is returned in the response. See `test/test.cloud.http` for more examples.

### Getting the URL and Chat Function Key

After deployment, get the function app hostname and the `chat` function key using the Azure CLI:

```bash
# Get the function app name from azd
FUNC_NAME=$(azd env get-value AZURE_FUNCTION_NAME)

# Get the resource group
RG=$(az functionapp list --query "[?name=='$FUNC_NAME'].resourceGroup" -o tsv)

# Get the base URL
HOST=$(az functionapp show --name "$FUNC_NAME" --resource-group "$RG" --query defaultHostName -o tsv)
echo "https://$HOST"

# Get the chat function key
az functionapp function keys list --name "$FUNC_NAME" --resource-group "$RG" --function-name chat --query default -o tsv
```

Use these values to populate `@baseUrl` and `@defaultKey` in `test/test.cloud.http`.

## What Else You Can Do

Because the agent is deployed to Azure Functions, you can:

- **Expose it as an MCP endpoint** for other agents to call
- **Add enterprise authentication** with Microsoft Entra ID
- **Scale it based on demand** with serverless auto-scaling
- **Write custom Python tools** that get deployed alongside the agent (see `src/tools/` for an example)

## Known Limitations

- **This is an experiment.** The runtime, APIs, and deployment model are under active development and may change significantly.
- **Python tools in `src/tools/` do not work locally.** Custom Python tools only run in the cloud runtime. They are fully functional after deploying with `azd up`.
- **Use `azd up`, not `azd provision` + `azd deploy` separately.** The pre-package hook scripts don't run in the correct sequence when provision and deploy are executed independently.
- **Windows is not supported.** The packaging hooks are shell scripts (`.sh`) and require macOS, Linux, or WSL.

## The Vision

The developer focuses entirely on the agent logic — `AGENTS.md`, skills, MCP servers, tools — and the platform handles hosting, scaling, auth, networking, and monitoring. The same source code runs locally in GitHub Copilot and remotely as an HTTP API on Azure Functions. No SDKs. No cloud frameworks. No rewrites. The agent format is the programming model.

## Try It

1. Clone this repo
2. Explore the `src` folder to see the agent definition
3. Open `src` in VS Code and chat with the agent locally (MCP and skills work; Python tools require cloud deployment)
4. Run `azd up` to deploy to Azure Functions
5. Open your cloud-hosted chat UI at `/`
6. Optionally call `/agent/chat` directly (see `test/test.cloud.http` for examples)
