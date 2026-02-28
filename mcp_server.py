"""
MCP (Model Context Protocol) Server Implementation
Provides SSE-based JSON-RPC 2.0 interface for Claude Desktop
"""
import json
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class MCPMethod(str, Enum):
    """MCP Protocol Methods"""
    INITIALIZE = "initialize"
    TOOLS_LIST = "tools/list"
    TOOLS_CALL = "tools/call"
    RESOURCES_LIST = "resources/list"
    RESOURCES_READ = "resources/read"
    PROMPTS_LIST = "prompts/list"
    PROMPTS_GET = "prompts/get"


@dataclass
class MCPTool:
    """MCP Tool Definition"""
    name: str
    description: str
    inputSchema: Dict[str, Any]


class MCPServer:
    """Model Context Protocol Server"""
    
    def __init__(self, zabbix_client):
        self.zabbix_client = zabbix_client
        self.server_info = {
            "name": "zabbix-mcp-server",
            "version": "1.0.0"
        }
        self._tools_cache: Optional[List[MCPTool]] = None
    
    def _get_tools(self) -> List[Dict[str, Any]]:
        """
        Generate MCP tools from available Zabbix operations
        Dynamically creates tools based on readonly mode
        """
        readonly = self.zabbix_client.readonly
        
        tools = [
            # System & Auth
            {
                "name": "get_zabbix_version",
                "description": "Get Zabbix API version",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            # Hosts - Read
            {
                "name": "get_hosts",
                "description": "List all monitored hosts with optional filters",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Filter by host name"},
                        "groupids": {"type": "array", "items": {"type": "string"}, "description": "Filter by group IDs"}
                    },
                    "required": []
                }
            },
            {
                "name": "get_host_by_name",
                "description": "Get details of a specific host by name",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "hostname": {"type": "string", "description": "Name of the host"}
                    },
                    "required": ["hostname"]
                }
            },
            # Problems
            {
                "name": "get_problems",
                "description": "Get current problems/active issues in Zabbix",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "hostids": {"type": "array", "items": {"type": "string"}, "description": "Filter by host IDs"},
                        "severities": {"type": "array", "items": {"type": "integer"}, "description": "Filter by severity (0-5)"}
                    },
                    "required": []
                }
            },
            # Items
            {
                "name": "get_items",
                "description": "Get monitoring items (metrics) for hosts",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "hostids": {"type": "array", "items": {"type": "string"}, "description": "Filter by host IDs"}
                    },
                    "required": []
                }
            },
            # Triggers
            {
                "name": "get_triggers",
                "description": "Get triggers (alert conditions) with optional filters",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "hostids": {"type": "array", "items": {"type": "string"}, "description": "Filter by host IDs"},
                        "active_only": {"type": "boolean", "description": "Show only active triggers"},
                        "min_severity": {"type": "integer", "minimum": 0, "maximum": 5, "description": "Minimum severity"}
                    },
                    "required": []
                }
            },
            # History
            {
                "name": "get_history",
                "description": "Get historical monitoring data for items",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "itemids": {"type": "array", "items": {"type": "string"}, "description": "Item IDs to get history for"},
                        "history_type": {"type": "integer", "enum": [0, 1, 2, 3, 4], "description": "0=float, 1=string, 2=log, 3=int, 4=text"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 10, "description": "Number of records"}
                    },
                    "required": ["itemids"]
                }
            },
            # Events
            {
                "name": "get_events",
                "description": "Get events from Zabbix event log",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "hostids": {"type": "array", "items": {"type": "string"}, "description": "Filter by host IDs"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 100}
                    },
                    "required": []
                }
            },
            # Groups
            {
                "name": "get_hostgroups",
                "description": "List host groups (organizational units)",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            # Templates
            {
                "name": "get_templates",
                "description": "List monitoring templates",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            # Maintenance
            {
                "name": "get_maintenances",
                "description": "List maintenance periods (scheduled downtime)",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            # Users
            {
                "name": "get_users",
                "description": "List Zabbix users",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            # Alerts
            {
                "name": "get_alerts",
                "description": "Get sent alerts/notifications",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 100}
                    },
                    "required": []
                }
            }
        ]
        
        # Add write operations only if NOT in readonly mode
        if not readonly:
            write_tools = [
                # Host Management
                {
                    "name": "create_host",
                    "description": "Create a new host in Zabbix for monitoring",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "host": {"type": "string", "description": "Technical name of the host"},
                            "groups": {"type": "array", "items": {"type": "object"}, "description": "Host groups"},
                            "interfaces": {"type": "array", "items": {"type": "object"}, "description": "Network interfaces"}
                        },
                        "required": ["host", "groups", "interfaces"]
                    }
                },
                {
                    "name": "delete_host",
                    "description": "Delete a host from Zabbix",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "hostids": {"type": "array", "items": {"type": "string"}, "description": "Host IDs to delete"}
                        },
                        "required": ["hostids"]
                    }
                },
                # Problem Management
                {
                    "name": "acknowledge_event",
                    "description": "Acknowledge problems/events with optional message",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "eventids": {"type": "array", "items": {"type": "string"}, "description": "Event IDs to acknowledge"},
                            "message": {"type": "string", "default": "", "description": "Acknowledgment message"},
                            "action": {"type": "integer", "default": 6, "description": "Action flags (6=ack+message)"}
                        },
                        "required": ["eventids"]
                    }
                },
                # Maintenance
                {
                    "name": "create_maintenance",
                    "description": "Create a maintenance period (scheduled downtime)",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Maintenance period name"},
                            "active_since": {"type": "integer", "description": "Start time (Unix timestamp)"},
                            "active_till": {"type": "integer", "description": "End time (Unix timestamp)"},
                            "hostids": {"type": "array", "items": {"type": "string"}, "description": "Host IDs"},
                            "groupids": {"type": "array", "items": {"type": "string"}, "description": "Group IDs"}
                        },
                        "required": ["name", "active_since", "active_till"]
                    }
                }
            ]
            tools.extend(write_tools)
        
        return tools
    
    async def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming MCP JSON-RPC 2.0 request"""
        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")
        
        try:
            if method == MCPMethod.INITIALIZE:
                result = await self._handle_initialize(params)
            elif method == MCPMethod.TOOLS_LIST:
                result = await self._handle_tools_list(params)
            elif method == MCPMethod.TOOLS_CALL:
                result = await self._handle_tools_call(params)
            elif method == MCPMethod.RESOURCES_LIST:
                result = {"resources": []}
            elif method == MCPMethod.RESOURCES_READ:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32601, "message": "No resources available"}
                }
            elif method == MCPMethod.PROMPTS_LIST:
                result = {"prompts": []}
            elif method == MCPMethod.PROMPTS_GET:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32601, "message": "No prompts available"}
                }
            elif method == "notifications/initialized":
                # Client notification after initialize - no response needed
                return None
            elif method == "ping":
                result = {}
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"}
                }
            
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": result
            }
        
        except Exception as e:
            logger.error(f"Error handling MCP request: {e}", exc_info=True)
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32603,
                    "message": str(e)
                }
            }
    
    async def _handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle initialize method"""
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {}
            },
            "serverInfo": self.server_info
        }
    
    async def _handle_tools_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/list method"""
        tools = self._get_tools()
        return {"tools": tools}
    
    async def _handle_tools_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/call method - execute Zabbix operations"""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        # Map tool names to Zabbix client methods
        try:
            if tool_name == "get_zabbix_version":
                result = await self.zabbix_client.get_api_version()
                return {"content": [{"type": "text", "text": f"Zabbix API Version: {result}"}]}
            
            elif tool_name == "get_hosts":
                result = await self.zabbix_client.get_hosts(**arguments)
                return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
            
            elif tool_name == "get_host_by_name":
                result = await self.zabbix_client.get_host_by_name(arguments["hostname"])
                return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
            
            elif tool_name == "get_problems":
                hostids = arguments.get("hostids")
                severities = arguments.get("severities")
                result = await self.zabbix_client.get_problems(hostids=hostids, severities=severities)
                return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
            
            elif tool_name == "get_items":
                hostids = arguments.get("hostids")
                result = await self.zabbix_client.get_items(hostids=hostids)
                return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
            
            elif tool_name == "get_triggers":
                result = await self.zabbix_client.get_triggers(**arguments)
                return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
            
            elif tool_name == "get_history":
                result = await self.zabbix_client.get_history(**arguments)
                return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
            
            elif tool_name == "get_events":
                hostids = arguments.get("hostids")
                limit = arguments.get("limit", 100)
                result = await self.zabbix_client.get_events(hostids=hostids, limit=limit)
                return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
            
            elif tool_name == "get_hostgroups":
                result = await self.zabbix_client.get_hostgroups()
                return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
            
            elif tool_name == "get_templates":
                result = await self.zabbix_client.get_templates()
                return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
            
            elif tool_name == "get_maintenances":
                result = await self.zabbix_client.get_maintenances()
                return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
            
            elif tool_name == "get_users":
                result = await self.zabbix_client.get_users()
                return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
            
            elif tool_name == "get_alerts":
                limit = arguments.get("limit", 100)
                result = await self.zabbix_client.get_alerts(limit=limit)
                return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
            
            # Write operations
            elif tool_name == "create_host":
                result = await self.zabbix_client.create_host(**arguments)
                return {"content": [{"type": "text", "text": f"Host created successfully: {json.dumps(result, indent=2)}"}]}
            
            elif tool_name == "delete_host":
                result = await self.zabbix_client.delete_host(arguments["hostids"])
                return {"content": [{"type": "text", "text": f"Host deleted successfully: {json.dumps(result, indent=2)}"}]}
            
            elif tool_name == "acknowledge_event":
                result = await self.zabbix_client.acknowledge_event(**arguments)
                return {"content": [{"type": "text", "text": f"Event acknowledged: {json.dumps(result, indent=2)}"}]}
            
            elif tool_name == "create_maintenance":
                result = await self.zabbix_client.create_maintenance(**arguments)
                return {"content": [{"type": "text", "text": f"Maintenance created: {json.dumps(result, indent=2)}"}]}
            
            else:
                raise ValueError(f"Unknown tool: {tool_name}")
        
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}", exc_info=True)
            return {"content": [{"type": "text", "text": f"Error: {str(e)}"}], "isError": True}
