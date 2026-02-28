# Quick Start Guide - MCP Integration

## 🚀 Testing the MCP Implementation

### 1. Start the Server

```bash
python main.py
```

The server will start on port 8000 with both REST and MCP endpoints.

### 2. Test MCP Endpoints with curl

**Test MCP initialization:**
```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0.0"}}}'
```

**Get list of available tools:**
```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}'
```

**Execute a tool:**
```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"get_zabbix_version","arguments":{}}}'
```

**Test SSE endpoint:**
```bash
curl http://localhost:8000/sse
# Expected output:
# event: endpoint
# data: http://localhost:8000/mcp
# 
# event: message
# data: {"jsonrpc":"2.0","method":"notifications/message","params":{"level":"info","logger":"mcp-server","data":"Zabbix MCP server ready"}}
# 
# : keepalive
# (connection stays open - press Ctrl+C to close)
```

### 3. Configure Claude Desktop

1. Find your Claude Desktop config file:
   - **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
   - **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **Linux**: `~/.config/Claude/claude_desktop_config.json`
   
   > For newer Claude Desktop versions, you may also use `mcp.json` in the same directory.

2. Copy the content from `mcp.json` or add manually:
   ```json
   {
     "mcpServers": {
       "zabbix": {
         "url": "http://localhost:8000/sse"
       }
     }
   }
   ```
   
   > The `url` points to the SSE endpoint. The client discovers the JSON-RPC endpoint (`/mcp`) automatically via the `event: endpoint` SSE message.

3. Restart Claude Desktop

4. In Claude, you should now see "Zabbix" available as a tool source

### 4. Test with Claude Desktop

Once configured, you can ask Claude things like:
- "What version of Zabbix are we running?"
- "Show me all hosts in Zabbix"
- "Are there any active problems?"
- "Get me the list of triggers"
- "Show me recent alerts"

If `ZABBIX_READONLY=true`, Claude will only see read-only tools.
If `ZABBIX_READONLY=false`, Claude will also have access to:
- Create hosts
- Delete hosts
- Acknowledge events
- Create maintenance windows

## 🔍 Troubleshooting

### MCP endpoint returns error
- Check that the server is running
- Verify your .env configuration
- Check server logs for detailed error messages

### Claude Desktop doesn't see the server
- Verify the config file location is correct
- Check that the JSON is valid
- Restart Claude Desktop after configuration changes
- Make sure the server is running and reachable

### Tools return errors
- Check Zabbix connection in .env file
- Verify ZABBIX_API_TOKEN or ZABBIX_USER/ZABBIX_PASSWORD
- Test Zabbix connection: `curl http://localhost:8000/api/version`

### SSE connection issues
- SSE connections are persistent and provide a channel for server-to-client notifications
- The endpoint returns `text/event-stream` content type
- **REQUIRED first message**: `event: endpoint` with the JSON-RPC URL (MCP spec requirement)
- **Optional messages**: `event: message` for JSON-RPC 2.0 notifications
- **Keepalive**: Comment lines (`: keepalive`) are sent every 30 seconds
- The SSE channel stays open for the duration of the session
- If Claude doesn't connect, verify:
  1. Server is running on the correct port
  2. URL in `mcp.json` is correct (`http://localhost:8000/sse`)
  3. First SSE message is `event: endpoint` with URL
  4. No firewall blocking the connection
- Test with curl to verify the endpoint responds correctly

## 📝 Architecture

```
Claude Desktop
    |
    | (1) Opens SSE connection to /sse
    v
/sse endpoint
    |
    | SENDS (REQUIRED by MCP):
    | event: endpoint
    | data: http://localhost:8000/mcp
    |
    | SENDS (optional notifications):
    | event: message
    | data: {"jsonrpc":"2.0","method":"notifications/message","params":{...}}
    |
    | MAINTAINS connection:
    | : keepalive (every 30s)
    |
Claude now knows endpoint URL and keeps SSE open
    |
    | (2) Sends JSON-RPC requests to endpoint URL (separate HTTP POST)
    v
POST http://localhost:8000/mcp
    |
    | Request: {"jsonrpc":"2.0","method":"initialize","params":{...}}
    | Response: {"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2024-11-05",...}}
    |
    | Request: {"jsonrpc":"2.0","method":"tools/list","id":2}
    | Response: {"jsonrpc":"2.0","id":2,"result":{"tools":[...]}}
    |
    | Request: {"jsonrpc":"2.0","method":"tools/call","id":3,"params":{...}}
    | Response: {"jsonrpc":"2.0","id":3,"result":{...}}
    v
MCPServer.handle_request()
    |
    | Routes to: _handle_initialize(), _handle_tools_list(), _handle_tools_call()
    v
ZabbixClient methods
    |
    | get_hosts(), get_problems(), create_host(), etc.
    v
Zabbix Server (JSON-RPC API)
```

**Key Points:**
- SSE (`/sse`) provides server→client notification channel (persistent connection)
- **First SSE message MUST be `event: endpoint` with the JSON-RPC URL** (MCP requirement)
- JSON-RPC requests (`/mcp`) are separate HTTP POST calls for client→server commands
- Both use JSON-RPC 2.0 format but serve different purposes
- SSE stays open throughout the session, enabling real-time server notifications

## ✨ Key Features

1. **Dual Protocol Support**: REST API and MCP work simultaneously
2. **Dynamic Tool List**: Tools adapt based on `ZABBIX_READONLY` setting
3. **SSE Streaming**: Compliant with MCP specification using JSON-RPC 2.0 over SSE
4. **Full JSON-RPC 2.0**: Compliant with MCP specification
5. **Error Handling**: Proper error codes and messages
6. **Security**: Respects read-only mode in both protocols

### SSE Format Details

The SSE endpoint follows the MCP SSE Transport specification:
- **Content-Type**: `text/event-stream`
- **REQUIRED First Event**: `event: endpoint` with JSON-RPC endpoint URL
  - Format: `event: endpoint\ndata: <url>\n\n`
  - This tells the MCP client where to send JSON-RPC requests
  - **Critical**: Without this, MCP clients won't know where to send requests
- **Optional Events**: `event: message` for server notifications
  - Format: `event: message\ndata: <json-rpc-notification>\n\n`
  - JSON-RPC 2.0 notifications for status updates
- **Keepalive**: Comment lines (`: keepalive\n\n`) every 30 seconds
- **CORS**: Enabled with `Access-Control-Allow-Origin: *`

**MCP SSE Protocol Flow:**
1. Client opens SSE connection → Server **MUST** send `event: endpoint` with URL
2. Client extracts endpoint URL from SSE message
3. Client sends `initialize` request to that URL → Server responds with capabilities
4. Client sends `tools/list` request → Server responds with available tools
5. Client sends `tools/call` requests → Server executes and responds
6. SSE stays open throughout, server can push notifications anytime

**Example SSE message sequence:**
```
event: endpoint
data: http://localhost:8000/mcp

event: message
data: {"jsonrpc":"2.0","method":"notifications/message","params":{"level":"info","logger":"mcp-server","data":"Zabbix MCP server ready"}}

: keepalive

```

**Why the endpoint event is critical:**
- MCP clients use SSE for discovery - they learn the JSON-RPC endpoint URL via SSE
- Without it, the client doesn't know where to send JSON-RPC requests
- This enables dynamic endpoint configuration and load balancing

This implementation is **100% compliant** with the MCP SSE transport specification.

## 📚 Resources

- [Model Context Protocol Specification](https://modelcontextprotocol.io)
- [Claude Desktop Documentation](https://docs.anthropic.com/claude/docs)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Zabbix API Documentation](https://www.zabbix.com/documentation/current/en/manual/api)
