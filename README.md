# Zabbix MCP Server

MCP (Model Context Protocol) server to connect LLM systems with Zabbix via REST API with OpenAPI 3.1.

## 🚀 Features

- **FastAPI**: High-performance REST server with automatic OpenAPI 3.1 documentation
- **MCP Protocol**: Full support for Model Context Protocol (Claude Desktop compatible)
- **Dual Protocol Support**: Simultaneous REST API and MCP/SSE endpoints
- **Open-WebUI Compatible**: Designed for open-webui integration on port 8000
- **Zabbix JSON-RPC Client**: Complete communication with Zabbix API
- **Managed Authentication**: Support for API tokens or username/password with automatic renewal
- **Read-Only Mode**: Optional security feature to prevent write operations on Zabbix
- **Complete API**: Over 40 endpoints for all Zabbix operations
  - **Full CRUD** for hosts, items, triggers, templates, host groups
  - **Monitoring**: Problems, history, trends, events, alerts
  - **Automation**: Maintenance, actions, scripts, discovery
  - **Management**: Users, services, proxies, graphs, dashboards
- **Detailed Descriptions**: Every endpoint has complete documentation to facilitate LLM usage
- **CORS Enabled**: Ready for web integrations
- **Interactive Documentation**: Swagger UI and ReDoc included
- **LLM-Ready**: Optimized for tool calling from LLM systems (OpenAI, Claude, etc.)

## 📋 Prerequisites

- Python 3.8 or higher
- Access to a Zabbix server with API enabled
- Zabbix user credentials with appropriate permissions

## 🔧 Installation

1. **Clone or navigate to the project directory:**
   ```bash
   cd ZABBIX-MCP
   ```

2. **Create a Python virtual environment:**
   ```bash
   python -m venv venv
   ```

3. **Activate the virtual environment:**
   - Windows:
     ```bash
     venv\Scripts\activate
     ```
   - Linux/Mac:
     ```bash
     source venv/bin/activate
     ```

4. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

5. **Configure environment variables:**
   - Copy the `.env.example` file to `.env`:
     ```bash
     copy .env.example .env
     ```
   - Edit `.env` with your Zabbix configuration:
     ```env
     ZABBIX_URL=https://your-zabbix-server.com/zabbix/api_jsonrpc.php
     # Use API token (recommended method)
     ZABBIX_API_TOKEN=your_api_token_here
     # Or username/password (legacy method)
     # ZABBIX_USER=your_username
     # ZABBIX_PASSWORD=your_password
     
     # SSL/TLS verification (set to false if using self-signed certificates)
     ZABBIX_VERIFY_SSL=true
     
     # Read-Only Mode (set to true to prevent any write operations on Zabbix)
     ZABBIX_READONLY=false
     
     SERVER_HOST=0.0.0.0
     SERVER_PORT=8000
     ```

   **How to obtain an API token in Zabbix:**
   - Log in to Zabbix as administrator
   - Go to Administration → General → API tokens
   - Click "Create API token"
   - Select the user and set expiration (or leave empty for permanent token)
   - Copy the generated token and insert it in the `.env` file

## 🚀 Starting the Server

```bash
python main.py
```

or with uvicorn directly:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The server will be available at `http://localhost:8000`

## 📚 API Documentation

Once the server is started, you can access the interactive documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI Schema**: http://localhost:8000/openapi.json

## 🔒 Read-Only Mode

The server supports a **read-only mode** that prevents any write operations on Zabbix. This is useful for:
- **Security**: Prevent accidental modifications to your monitoring infrastructure
- **Training**: Allow users to explore and learn without risk of breaking configurations
- **Auditing**: Provide read-only access for monitoring and reporting purposes
- **LLM Safety**: Prevent AI assistants from making unauthorized changes

### How to Enable Read-Only Mode

Set the `ZABBIX_READONLY` flag to `true` in your `.env` file:

```env
ZABBIX_READONLY=true
```

### What Gets Blocked

When read-only mode is enabled, all write operations are blocked, including:
- Creating, updating, or deleting hosts
- Creating, updating, or deleting items, triggers, templates
- Creating or deleting host groups
- Acknowledging problems
- Creating or deleting maintenance windows
- Creating, updating, or deleting users
- Creating or deleting actions
- Any other operation that modifies Zabbix data

**Additionally, write endpoints are automatically hidden from OpenAPI documentation** (Swagger UI and ReDoc), so LLM systems and API consumers only see the available read-only operations.

### What Still Works

All read operations continue to work normally:
- Listing hosts, items, triggers, problems
- Viewing historical data and trends
- Checking API version and authentication
- Viewing events, alerts, graphs, dashboards
- All GET operations

### Error Response

When attempting a write operation in read-only mode, the API returns:
- **HTTP Status**: 403 Forbidden
- **Response**:
  ```json
  {
    "error": "Operation Forbidden",
    "detail": "Cannot perform 'operation_name' operation: System is in read-only mode. Set ZABBIX_READONLY=false in .env to enable write operations."
  }
  ```
## 🤖 MCP / Claude Desktop Integration

This server implements the **Model Context Protocol (MCP)** for integration with Claude Desktop and other AI assistants.

### What is MCP?

MCP (Model Context Protocol) is a JSON-RPC 2.0 based protocol that allows AI assistants like Claude to discover and use external tools. It provides:

- **Standardized tool discovery** - AI can query available operations
- **Dynamic capabilities** - Tools adapt based on server mode (read-only vs full access)
- **Streaming support** - SSE (Server-Sent Events) for persistent connections

### MCP Endpoints

- **POST /mcp** - Main MCP endpoint for JSON-RPC 2.0 requests (initialize, tools/list, tools/call)
- **GET /sse** - Server-Sent Events endpoint for persistent connection and server notifications

**MCP SSE Protocol (fully compliant):**
1. Claude Desktop opens an SSE connection to `/sse`
2. Server **MUST** send `event: endpoint` with the JSON-RPC endpoint URL (e.g., `http://localhost:8000/mcp`)
3. Client discovers the endpoint URL from this SSE message
4. Client sends JSON-RPC requests to the discovered endpoint:
   - `initialize` → Server responds with capabilities
   - `tools/list` → Server responds with available tools
   - `tools/call` → Server executes operations and responds
5. SSE connection stays open throughout for server-to-client notifications
6. Keepalive messages (`: keepalive`) are sent every 30 seconds to maintain the connection

**Why SSE?**
- Enables dynamic endpoint discovery (client learns URL via SSE)
- Provides persistent channel for server→client notifications
- Allows server to push updates when state changes (e.g., new tools available)

### Claude Desktop Setup

1. **Locate Claude Desktop configuration directory**:
   - Windows: `%APPDATA%\Claude\claude_desktop_config.json`
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Linux: `~/.config/Claude/claude_desktop_config.json`

   > **Alternative**: For newer Claude Desktop versions, you may also use `mcp.json` in the same directory.

2. **Add this server to the configuration**:
   ```json
   {
     "mcpServers": {
       "zabbix": {
         "url": "http://localhost:8000/sse"
       }
     }
   }
   ```
   
   You can also copy the provided `mcp.json` file.
   
   > **Note:** The `url` points to the SSE endpoint. Claude Desktop connects via SSE and automatically discovers the JSON-RPC endpoint (`/mcp`) from the `event: endpoint` message.

3. **Restart Claude Desktop** to load the new server configuration

### Available MCP Tools

**Read-only tools** (always available):
- `get_zabbix_version` - Get Zabbix API version
- `get_hosts` - List all hosts with filters
- `get_host_by_name` - Get host details by name
- `get_problems` - Get active problems/issues
- `get_items` - Get monitoring items
- `get_triggers` - Get configured triggers
- `get_history` - Get item history data
- `get_events` - Get Zabbix events
- `get_hostgroups` - List host groups
- `get_templates` - List templates
- `get_maintenances` - List maintenance windows
- `get_users` - List Zabbix users
- `get_alerts` - Get alert history

**Write tools** (disabled when `ZABBIX_READONLY=true`):
- `create_host` - Create a new host
- `delete_host` - Delete a host
- `acknowledge_event` - Acknowledge an event/problem
- `create_maintenance` - Create a maintenance window

### Testing MCP Integration

```bash
# Test MCP initialization
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0.0"}}}'

# Test tool discovery
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}'

# Test tool execution - Get Zabbix version
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"get_zabbix_version","arguments":{}}}'

# Test tool execution - Get hosts
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"get_hosts","arguments":{}}}'

# Test SSE endpoint
curl http://localhost:8000/sse
# Expected output:
# event: endpoint
# data: http://localhost:8000/mcp
# 
# event: message
# data: {"jsonrpc":"2.0","method":"notifications/message","params":{"level":"info","logger":"mcp-server","data":"Zabbix MCP server ready"}}
# 
# : keepalive
# (connection stays open)
```

### Dual Protocol Support

This server supports **both OpenAPI REST and MCP** simultaneously:

**OpenAPI REST** (`/api/*`) - For web clients, tools, direct API access:
- Automatic documentation at `/docs` and `/redoc`
- Standard HTTP methods (GET, POST, PUT, DELETE)
- JSON request/response format
- Complete CRUD operations

**MCP Protocol** (`/mcp`, `/sse`) - For AI assistants like Claude Desktop:
- JSON-RPC 2.0 protocol
- SSE for endpoint discovery and notifications
- Tool discovery and dynamic capabilities
- **100% MCP specification compliant**
- AI-optimized tool descriptions

Both protocols respect the `ZABBIX_READONLY` configuration. Choose the protocol that best fits your use case.

## 🔌 Main Endpoints

### System
- `GET /health` - Server health check
- `GET /api/version` - Zabbix API version

### Authentication
- `POST /api/auth` - Authenticate with Zabbix

### Hosts (Complete Management)
- `GET /api/hosts` - List all hosts
- `GET /api/hosts/{hostname}` - Details of a specific host
- `POST /api/hosts` - Create a new host
- `PUT /api/hosts/{hostid}` - Update a host
- `DELETE /api/hosts/{hostid}` - Delete a host
- `POST /api/hosts/{hostid}/enable` - Enable monitoring
- `POST /api/hosts/{hostid}/disable` - Disable monitoring

### Items (Monitoring Metrics)
- `GET /api/items` - List monitoring items
- `POST /api/items` - Create a new item
- `DELETE /api/items/{itemid}` - Delete an item

### Triggers (Alert Conditions)
- `GET /api/triggers` - List triggers with optional filters
- `POST /api/triggers` - Create a new trigger
- `DELETE /api/triggers/{triggerid}` - Delete a trigger

### Problems (Active Issues)
- `GET /api/problems` - Current problems
- `POST /api/problems/acknowledge` - Acknowledge problems

### History & Trends (Historical Data)
- `POST /api/history` - Detailed historical data for items
- `GET /api/trends` - Hourly aggregated data (trends)

### Events (System Events)
- `GET /api/events` - Events from Zabbix log

### Host Groups (Organizational Groups)
- `GET /api/hostgroups` - List host groups
- `POST /api/hostgroups` - Create a new group
- `DELETE /api/hostgroups/{groupid}` - Delete a group

### Templates (Reusable Configurations)
- `GET /api/templates` - List Zabbix templates
- `POST /api/templates` - Create a new template
- `DELETE /api/templates/{templateid}` - Delete a template

### Maintenance (Maintenance Windows)
- `GET /api/maintenances` - List maintenance periods
- `POST /api/maintenances` - Create a scheduled maintenance
- `DELETE /api/maintenances/{maintenanceid}` - Delete maintenance

### Users & Access (Users and Access)
- `GET /api/users` - List Zabbix users

### Alerts (Sent Notifications)
- `GET /api/alerts` - History of sent notifications

### Actions (Automatic Actions)
- `GET /api/actions` - List configured automatic actions

### Services (IT/Business Services)
- `GET /api/services` - Business services and SLA

### Graphs & Visualization (Visualization)
- `GET /api/graphs` - Configured graphs
- `GET /api/maps` - Network maps
- `GET /api/dashboards` - Configured dashboards

### Scripts (Remote Automation)
- `GET /api/scripts` - List available scripts
- `POST /api/scripts/{scriptid}/execute` - Execute script on a host

### Proxies (Distributed Monitoring)
- `GET /api/proxies` - List Zabbix proxies

### Discovery (Automatic Discovery)
- `GET /api/discovery/rules` - Low-Level Discovery rules
- `GET /api/discovery/hosts` - Hosts discovered from network
- `GET /api/discovery/services` - Services discovered from network

### Generic (Advanced Calls)
- `POST /api/call` - Generic call to Zabbix API

## 💡 Usage Examples

### Get Zabbix API version

```bash
curl http://localhost:8000/api/version
```

### Get all hosts

```bash
curl http://localhost:8000/api/hosts
```

### Get current problems

```bash
curl http://localhost:8000/api/problems
```

### Create a new host

```bash
curl -X POST http://localhost:8000/api/hosts \
  -H "Content-Type: application/json" \
  -d '{
    "host": "New-Server-01",
    "groups": [{"groupid": "2"}],
    "interfaces": [{
      "type": 1,
      "main": 1,
      "useip": 1,
      "ip": "192.168.1.100",
      "dns": "",
      "port": "10050"
    }]
  }'
```

### Create a monitoring item

```bash
curl -X POST http://localhost:8000/api/items \
  -H "Content-Type: application/json" \
  -d '{
    "hostid": "10001",
    "name": "CPU Load",
    "key": "system.cpu.load[,avg1]",
    "type": 0,
    "value_type": 0,
    "delay": "1m"
  }'
```

### Acknowledge a problem

```bash
curl -X POST http://localhost:8000/api/problems/acknowledge \
  -H "Content-Type: application/json" \
  -d '{
    "eventids": ["12345"],
    "message": "Working on it",
    "action": 6
  }'
```

### Create a scheduled maintenance

```bash
curl -X POST http://localhost:8000/api/maintenances \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Weekend Maintenance",
    "active_since": 1735344000,
    "active_till": 1735387200,
    "hostids": ["10001", "10002"]
  }'
```

### Get active triggers with high severity

```bash
curl "http://localhost:8000/api/triggers?active_only=true&min_severity=4"
```

### Get historical data

```bash
curl -X POST http://localhost:8000/api/history \
  -H "Content-Type: application/json" \
  -d '{
    "itemids": ["23456"],
    "history_type": 0,
    "limit": 100
  }'
```

### Generic Zabbix API call

```bash
curl -X POST http://localhost:8000/api/call \
  -H "Content-Type: application/json" \
  -d '{
    "method": "host.get",
    "params": {
      "output": ["hostid", "host"],
      "limit": 10
    }
  }'
```

## 🔗 Integration with Open-WebUI

The server is designed to be used with open-webui. Once started:

1. Configure open-webui to use the endpoint: `http://localhost:8000`
2. The server automatically exposes OpenAPI 3.1 documentation
3. All endpoints are documented and ready to use

## 🛠️ Development

### Project Structure

```
ZABBIX-MCP/
├── main.py                       # Main FastAPI server with REST and MCP endpoints
├── mcp_server.py                 # MCP protocol implementation
├── zabbix_client.py              # Client for Zabbix API
├── config.py                     # Application configuration
├── requirements.txt              # Python dependencies
├── .env.example                  # Configuration template
├── mcp.json                      # Claude Desktop MCP configuration
├── README.md                     # This documentation
├── LLM_GUIDE.md                  # Guide for LLM systems on endpoint usage
├── MCP_QUICKSTART.md             # Quick start guide for MCP integration
├── LICENSE                       # MIT License
├── routers/                      # API route modules
│   ├── __init__.py
│   ├── hosts.py
│   ├── items.py
│   ├── triggers.py
│   ├── problems.py
│   ├── history.py
│   ├── system.py
│   └── other.py
└── .env                          # Local configuration (not committed)
```

### Adding New Endpoints

1. Add the method in `zabbix_client.py` if necessary
2. Create the endpoint in `main.py` with `@app.get()` or `@app.post()` decorator
3. Use Pydantic models for request/response validation
4. Handle `ZabbixAPIError` exceptions

## 🔒 Security

- **Authentication:** The server supports both API tokens and username/password
  - **Recommended:** Use API token (more secure, can be easily revoked)
  - **Legacy:** Username/password (token expires after 1 hour)
- Credentials are managed through environment variables
- Never commit the `.env` file to the repository
- Use HTTPS in production to protect credentials
- Consider implementing authentication for the MCP server
- API tokens can be configured with expiration dates in Zabbix

## 📝 Notes

- The server supports both **API tokens** (recommended) and **username/password** for authentication
- API tokens don't expire (if configured that way in Zabbix), tokens from username/password expire after 1 hour
- The server disables SSL verification for the Zabbix client (`verify=False`). In production, configure appropriate certificates.
- HTTP request timeout is set to 30 seconds.

## 🐛 Troubleshooting

### Connection error to Zabbix

Verify that:
- The Zabbix URL is correct and reachable
- Credentials are correct
- The Zabbix user has necessary permissions

### Port 8000 already in use

Change the port in the `.env` file:
```env
SERVER_PORT=8080
```

## 📄 License

MIT License

## 🤝 Contributions

Contributions, issues and feature requests are welcome!
