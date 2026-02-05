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

```bash
azd up
```

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
