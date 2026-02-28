# LLM Guide: Using the Zabbix MCP Server

This guide helps LLM systems understand when and how to use the Zabbix MCP Server endpoints.

## Endpoint Categorization by Scenario

### 🚨 "What's going wrong?" / "Are there any problems?"
**Endpoints to use:**
- `GET /api/problems` - Show all current problems
- `GET /api/triggers?active_only=true` - Triggers currently in problem state
- `GET /api/alerts` - Recently sent notifications

**Example questions:**
- "Are there any system problems?"
- "Show me active alerts"
- "Which hosts have problems?"
- "What's not working?"

### 📊 "How is server X doing?" / "Show metrics"
**Endpoints to use:**
- `GET /api/hosts/{hostname}` - Information about a specific host
- `GET /api/items?hostids=X` - Available metrics for the host
- `POST /api/history` - Recent metric values
- `GET /api/trends` - Trends over time

**Example questions:**
- "How is server web-01 doing?"
- "Show me database CPU"
- "What's the memory usage in the last few days?"

### 🔧 "Add a new server" / "Configure monitoring"
**Endpoints to use:**
- `POST /api/hosts` - Create a new host
- `POST /api/items` - Add metrics to monitor
- `POST /api/triggers` - Set alert conditions
- `GET /api/templates` - See available templates
- `GET /api/hostgroups` - See available groups

**Example questions:**
- "Add server 192.168.1.50 to monitoring"
- "Create an alert for high CPU"
- "Set up monitoring for the new database"

### 🛠️ "Do maintenance" / "Disable alerts"
**Endpoints to use:**
- `POST /api/maintenances` - Create maintenance window
- `POST /api/hosts/{hostid}/disable` - Temporarily disable a host
- `POST /api/problems/acknowledge` - Acknowledge a problem

**Example questions:**
- "Disable alerts for the weekend"
- "Put the server in maintenance"
- "Acknowledge this problem"
- "Pause monitoring for 2 hours"

### 📈 "Show statistics" / "Report"
**Endpoints to use:**
- `GET /api/hosts` - List all hosts
- `GET /api/problems` - Problems in the period
- `GET /api/events` - Event history
- `POST /api/history` - Historical data
- `GET /api/trends` - Aggregated trends
- `GET /api/alerts` - Sent notifications

**Example questions:**
- "How many hosts are we monitoring?"
- "How many problems have we had this week?"
- "Show server CPU history"

### 🗂️ "Organize" / "Manage configuration"
**Endpoints to use:**
- `GET /api/hostgroups` - See groups
- `POST /api/hostgroups` - Create groups
- `GET /api/templates` - See templates
- `PUT /api/hosts/{hostid}` - Modify host
- `GET /api/users` - User management

**Example questions:**
- "Create a group for production servers"
- "What templates do we have?"
- "Move this host to another group"

### 🔍 "Search" / "Find"
**Endpoints to use:**
- `GET /api/hosts?name=X` - Search host by name
- `GET /api/hosts` - List all hosts
- `GET /api/items` - See all metrics
- `GET /api/triggers` - See all triggers

**Example questions:**
- "Find the server called web-01"
- "What hosts do we have in the datacenter?"
- "Search for CPU type items"

### 🚀 "Execute" / "Automate"
**Endpoints to use:**
- `GET /api/scripts` - See available scripts
- `POST /api/scripts/{scriptid}/execute` - Execute script
- `GET /api/actions` - See automatic actions

**Example questions:**
- "Run restart on server X"
- "What scripts can I execute?"
- "Launch automatic cleanup"

### 🌐 "Network discovery" / "Network discovery"
**Endpoints to use:**
- `GET /api/discovery/hosts` - Discovered hosts
- `GET /api/discovery/services` - Discovered services
- `GET /api/discovery/rules` - LLD rules

**Example questions:**
- "What devices did you find on the network?"
- "Show discovered services"
- "Is there anything new on the network?"

## Optimal Response Pattern

### 1. Always start with context
```
"I'm checking current problems in Zabbix..."
```

### 2. Call the appropriate endpoint
```python
GET /api/problems
```

### 3. Interpret and present results
```
"I found 3 active problems:
1. Server web-01: High CPU (90%) - Severity: High
2. Database-01: Low disk space - Severity: Warning
3. App-server: Service down - Severity: Disaster"
```

### 4. Offer next actions
```
"Would you like me to:
- Acknowledge these problems?
- See historical details?
- Put a server in maintenance?"
```

## Endpoint Combination

For complete answers, often multiple endpoints need to be combined:

### Example: "How is server web-01 doing?"
1. `GET /api/hosts/web-01` - Find the host and get the hostid
2. `GET /api/problems?hostids={hostid}` - Check active problems
3. `GET /api/items?hostids={hostid}` - See available metrics
4. `POST /api/history` - Get recent values of key metrics

### Example: "Add new server to monitoring"
1. `GET /api/hostgroups` - Show available groups
2. `GET /api/templates` - Show available templates
3. `POST /api/hosts` - Create the host with groups and templates
4. Confirm: "Server added successfully"

## Error Handling

If an endpoint returns an error:
1. Interpret the error for the user
2. Suggest solutions (e.g., "This host doesn't exist, do you want to search for it?")
3. Offer alternatives (e.g., "I'll try searching by name instead of ID")

## Best Practices

1. **Always use specific endpoints** instead of `/api/call` when possible
2. **Filter results** to avoid overwhelming the user
3. **Aggregate information** from multiple endpoints for complete answers
4. **Use appropriate limits** (e.g., limit=10 for previews, limit=100 for reports)
5. **Interpret severity codes**: 0-5 where 5 is the most severe
6. **Convert Unix timestamps** to readable dates for the user
7. **Suggest proactive actions** based on the data

## Problem Severity

- **5 (Disaster)**: Requires immediate action
- **4 (High)**: Important, should be handled soon
- **3 (Average)**: Normal priority
- **2 (Warning)**: Should be monitored
- **1 (Information)**: Informational
- **0 (Not classified)**: Not classified

## Final Tips

- **Be proactive**: If you see many problems, suggest creating a maintenance
- **Be contextual**: If a user asks about a server, they probably want to see its problems too
- **Be clear**: Always translate technical data into understandable language
- **Be efficient**: One well-made call is better than 10 separate calls
