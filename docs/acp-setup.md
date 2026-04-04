# ACP Setup

Glider for Mistral can be used in text editors and IDEs that support [Agent Client Protocol](https://agentclientprotocol.com/overview/clients). Glider for Mistral includes the `glider-acp` tool.
Once you have set up `glider` with the API keys, you are ready to use `glider-acp` in your editor. Below are the setup instructions for some editors that support ACP.

## Zed

For usage in Zed, we recommend using the [Glider for Mistral Zed's extension](https://zed.dev/extensions/mistral-glider). Alternatively, you can set up a local install as follows:

1. Go to `~/.config/zed/settings.json` and, under the `agent_servers` JSON object, add the following key-value pair to invoke the `glider-acp` command. Here is the snippet:

```json
{
   "agent_servers": {
      "Glider for Mistral": {
         "type": "custom",
         "command": "glider-acp",
         "args": [],
         "env": {}
      }
   }
}
```

1. In the `New Thread` pane on the right, select the `glider` agent and start the conversation.

## JetBrains IDEs

For using Glider for Mistral in JetBrains IDEs, you'll need to have the [Jetbrains AI Assistant extension](https://plugins.jetbrains.com/plugin/22282-jetbrains-ai-assistant) installed

### Version 2025.3 or later

1. Open settings, then go to `Tools > AI Assistant > Agents`. Search for `Glider for Mistral`, click install

2. Open AI Assistant. You should be able to select Glider for Mistral from the agent selector (if you're not authenticated yet, you will be prompted to do so).

### Legacy method

1. Add the following snippet to your JetBrains IDE acp.json ([documentation](https://www.jetbrains.com/help/ai-assistant/acp.html)):

```json
{
  "agent_servers": {
    "Glider for Mistral": {
      "command": "glider-acp",
    }
  }
}
```

1. In the AI Chat agent selector, select the new Glider for Mistral agent and start the conversation.

## Neovim (using avante.nvim)

Add Glider for Mistral in the acp_providers section of your configuration

```lua
{
  acp_providers = {
    ["mistral-glider"] = {
      command = "glider-acp",
      env = {
         MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY"), -- necessary if you setup Glider for Mistral manually
      },
    }
  }
}
```
