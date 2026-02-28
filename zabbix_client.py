"""
Zabbix API Client - Manages communication with Zabbix server via JSON-RPC
"""
import httpx
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from config import settings
import urllib3

# Disable SSL warnings if verify_ssl is False
if not settings.zabbix_verify_ssl:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


class ZabbixAPIError(Exception):
    """Custom exception for Zabbix API errors"""
    pass


class ReadOnlyModeError(Exception):
    """Exception raised when attempting write operations in read-only mode"""
    pass


class ZabbixClient:
    """Client for interacting with Zabbix API using JSON-RPC 2.0"""

    def __init__(self, url: str, api_token: Optional[str] = None, user: Optional[str] = None, password: Optional[str] = None):
        """
        Initialize Zabbix API client

        Args:
            url: Zabbix API endpoint URL
            api_token: Zabbix API token for authentication (recommended)
            user: Zabbix username for authentication (legacy)
            password: Zabbix password for authentication (legacy)
        """
        self.url = url
        self.api_token = api_token
        self.user = user
        self.password = password
        self.auth_token: Optional[str] = None  # Session token from username/password login
        self.token_expires: Optional[datetime] = None
        self.request_id = 1
        self.verify_ssl = settings.zabbix_verify_ssl
        self.readonly = settings.zabbix_readonly

    def _check_readonly(self, operation: str):
        """
        Check if the system is in read-only mode and raise exception if attempting write operation
        
        Args:
            operation: Name of the operation being attempted
            
        Raises:
            ReadOnlyModeError: If system is in read-only mode
        """
        if self.readonly:
            raise ReadOnlyModeError(
                f"Cannot perform '{operation}' operation: System is in read-only mode. "
                f"Set ZABBIX_READONLY=false in .env to enable write operations."
            )

    async def _make_request(self, method: str, params: Dict[str, Any] = None) -> Any:
        """
        Make a JSON-RPC request to Zabbix API

        Args:
            method: Zabbix API method name
            params: Parameters for the API method

        Returns:
            Response data from Zabbix API

        Raises:
            ZabbixAPIError: If the API returns an error
        """
        if params is None:
            params = {}

        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": self.request_id
        }

        headers = {"Content-Type": "application/json"}

        # Authentication - apiinfo.version doesn't need auth
        if method not in ["apiinfo.version", "user.login"]:
            if self.api_token:
                # Use Bearer token for Zabbix 6.4+ / 7.0+
                headers["Authorization"] = f"Bearer {self.api_token}"
            elif self.auth_token:
                # Use session token for username/password auth
                payload["auth"] = self.auth_token

        self.request_id += 1

        try:
            async with httpx.AsyncClient(verify=self.verify_ssl, timeout=30.0) as client:
                response = await client.post(
                    self.url,
                    json=payload,
                    headers=headers
                )
                response.raise_for_status()

            data = response.json()

            if "error" in data:
                error_msg = data["error"].get("message", "Unknown error")
                error_data = data["error"].get("data", "")
                error_code = data["error"].get("code", -1)
                detail = f"{error_msg}: {error_data}" if error_data else error_msg
                raise ZabbixAPIError(f"Zabbix API error [{error_code}]: {detail}")

            return data.get("result")

        except httpx.HTTPError as e:
            logger.error(f"HTTP error communicating with Zabbix: {e}")
            raise ZabbixAPIError(f"HTTP error: {str(e)}")
        except Exception as e:
            logger.error(f"Error communicating with Zabbix: {e}")
            raise ZabbixAPIError(f"Communication error: {str(e)}")

    async def authenticate(self) -> bool:
        """
        Authenticate with Zabbix API

        Returns:
            True if authentication successful

        Raises:
            ZabbixAPIError: If authentication fails
        """
        # If API token is already set, no need to authenticate
        if self.api_token:
            logger.info("Using provided API token for authentication")
            return True

        # Fall back to username/password authentication
        if not self.user or not self.password:
            raise ZabbixAPIError("API token or username/password required for authentication")

        try:
            result = await self._make_request(
                "user.login",
                {"username": self.user, "password": self.password}
            )
            self.auth_token = result
            self.token_expires = datetime.now() + timedelta(hours=1)
            logger.info("Successfully authenticated with Zabbix using username/password")
            return True
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            raise

    async def ensure_authenticated(self):
        """Ensure we have a valid authentication token"""
        # If using API token, it doesn't expire
        if self.api_token:
            return

        # For username/password auth, check expiration
        if not self.auth_token or (self.token_expires and datetime.now() >= self.token_expires):
            await self.authenticate()

    # API Version
    async def get_api_version(self) -> str:
        """Get Zabbix API version (no authentication required)"""
        return await self._make_request("apiinfo.version", {})

    # Host methods
    async def get_hosts(self, output: str = "extend", **kwargs) -> List[Dict[str, Any]]:
        """
        Get list of hosts from Zabbix

        Args:
            output: Output format (extend, shorten, refer to specific fields)
            **kwargs: Additional parameters for host.get

        Returns:
            List of hosts
        """
        await self.ensure_authenticated()
        params = {"output": output, **kwargs}
        return await self._make_request("host.get", params)

    async def get_host_by_name(self, hostname: str) -> Optional[Dict[str, Any]]:
        """Get a specific host by name"""
        await self.ensure_authenticated()
        hosts = await self.get_hosts(filter={"host": hostname})
        return hosts[0] if hosts else None

    # Item methods
    async def get_items(self, hostids: List[str] = None, output: str = "extend", **kwargs) -> List[Dict[str, Any]]:
        """
        Get items from Zabbix

        Args:
            hostids: List of host IDs to filter by
            output: Output format
            **kwargs: Additional parameters

        Returns:
            List of items
        """
        await self.ensure_authenticated()
        params = {"output": output, **kwargs}
        if hostids:
            params["hostids"] = hostids
        return await self._make_request("item.get", params)

    # Trigger methods
    async def get_triggers(self, hostids: List[str] = None, output: str = "extend", **kwargs) -> List[Dict[str, Any]]:
        """
        Get triggers from Zabbix

        Args:
            hostids: List of host IDs to filter by
            output: Output format
            **kwargs: Additional parameters

        Returns:
            List of triggers
        """
        await self.ensure_authenticated()
        params = {"output": output, **kwargs}
        if hostids:
            params["hostids"] = hostids
        return await self._make_request("trigger.get", params)

    async def get_active_triggers(self, min_severity: int = 0) -> List[Dict[str, Any]]:
        """
        Get active (problem) triggers

        Args:
            min_severity: Minimum severity level (0-5)

        Returns:
            List of active triggers
        """
        await self.ensure_authenticated()
        return await self.get_triggers(
            filter={"value": 1},  # 1 = PROBLEM
            min_severity=min_severity,
            skipDependent=1,
            monitored=1,
            active=1,
            expandDescription=1
        )

    # Problem methods
    async def get_problems(self, hostids: List[str] = None, severities: List[int] = None, **kwargs) -> List[Dict[str, Any]]:
        """
        Get problems from Zabbix

        Args:
            hostids: Filter by host IDs
            severities: Filter by severity levels
            **kwargs: Additional parameters

        Returns:
            List of problems
        """
        await self.ensure_authenticated()
        params = {"output": "extend", **kwargs}
        if hostids:
            params["hostids"] = hostids
        if severities:
            params["severities"] = severities
        return await self._make_request("problem.get", params)

    # History methods
    async def get_history(self, itemids: List[str], history_type: int = 0, limit: int = 10, **kwargs) -> List[Dict[str, Any]]:
        """
        Get history data

        Args:
            itemids: List of item IDs
            history_type: History object types (0=float, 1=string, 2=log, 3=integer, 4=text)
            limit: Number of records to return
            **kwargs: Additional parameters

        Returns:
            List of history records
        """
        await self.ensure_authenticated()
        params = {
            "output": "extend",
            "itemids": itemids,
            "history": history_type,
            "limit": limit,
            "sortfield": "clock",
            "sortorder": "DESC",
            **kwargs
        }
        return await self._make_request("history.get", params)

    # Event methods
    async def get_events(self, hostids: List[str] = None, limit: int = 100, **kwargs) -> List[Dict[str, Any]]:
        """
        Get events from Zabbix

        Args:
            hostids: Filter by host IDs
            limit: Maximum number of events
            **kwargs: Additional parameters

        Returns:
            List of events
        """
        await self.ensure_authenticated()
        params = {
            "output": "extend",
            "sortfield": "clock",
            "sortorder": "DESC",
            "limit": limit,
            **kwargs
        }
        if hostids:
            params["hostids"] = hostids
        return await self._make_request("event.get", params)

    # Template methods
    async def get_templates(self, output: str = "extend", **kwargs) -> List[Dict[str, Any]]:
        """Get templates from Zabbix"""
        await self.ensure_authenticated()
        params = {"output": output, **kwargs}
        return await self._make_request("template.get", params)

    # Hostgroup methods
    async def get_hostgroups(self, **kwargs) -> List[Dict[str, Any]]:
        """Get host groups from Zabbix. Use this to organize hosts into logical groups."""
        await self.ensure_authenticated()
        params = {**kwargs} if kwargs else {}
        return await self._make_request("hostgroup.get", params)

    async def create_hostgroup(self, name: str) -> Dict[str, Any]:
        """
        Create a new host group
        Use this when you need to organize hosts into a new logical group.

        Args:
            name: Name of the host group

        Returns:
            Created host group information with groupid
        """
        self._check_readonly("create_hostgroup")
        await self.ensure_authenticated()
        return await self._make_request("hostgroup.create", {"name": name})

    async def update_hostgroup(self, groupid: str, **kwargs) -> Dict[str, Any]:
        """
        Update an existing host group
        Use this to modify host group properties like name.

        Args:
            groupid: ID of the host group to update
            **kwargs: Properties to update

        Returns:
            Updated host group information
        """
        self._check_readonly("update_hostgroup")
        await self.ensure_authenticated()
        params = {"groupid": groupid, **kwargs}
        return await self._make_request("hostgroup.update", params)

    async def delete_hostgroup(self, groupids: List[str]) -> Dict[str, Any]:
        """
        Delete host groups
        Use this to remove host groups that are no longer needed.

        Args:
            groupids: List of host group IDs to delete

        Returns:
            Confirmation of deletion
        """
        self._check_readonly("delete_hostgroup")
        await self.ensure_authenticated()
        return await self._make_request("hostgroup.delete", groupids)

    # Host creation, update, delete
    async def create_host(self, host: str, groups: List[Dict[str, str]], interfaces: List[Dict[str, Any]], **kwargs) -> Dict[str, Any]:
        """
        Create a new host in Zabbix
        Use this to add a new server, device, or application to monitor.

        Args:
            host: Technical name of the host
            groups: List of host groups (e.g., [{"groupid": "2"}])
            interfaces: Network interfaces (e.g., [{"type": 1, "main": 1, "useip": 1, "ip": "192.168.1.1", "dns": "", "port": "10050"}])
            **kwargs: Additional properties like templates, macros, inventory

        Returns:
            Created host information with hostid
        """
        self._check_readonly("create_host")
        await self.ensure_authenticated()
        params = {"host": host, "groups": groups, "interfaces": interfaces, **kwargs}
        return await self._make_request("host.create", params)

    async def update_host(self, hostid: str, **kwargs) -> Dict[str, Any]:
        """
        Update an existing host
        Use this to modify host properties, add/remove groups, change interfaces, etc.

        Args:
            hostid: ID of the host to update
            **kwargs: Properties to update

        Returns:
            Updated host information
        """
        self._check_readonly("update_host")
        await self.ensure_authenticated()
        params = {"hostid": hostid, **kwargs}
        return await self._make_request("host.update", params)

    async def delete_host(self, hostids: List[str]) -> Dict[str, Any]:
        """
        Delete hosts from Zabbix
        Use this to remove hosts that are no longer monitored.

        Args:
            hostids: List of host IDs to delete

        Returns:
            Confirmation of deletion
        """
        self._check_readonly("delete_host")
        await self.ensure_authenticated()
        return await self._make_request("host.delete", hostids)

    async def enable_host(self, hostid: str) -> Dict[str, Any]:
        """
        Enable monitoring for a host
        Use this to resume monitoring a previously disabled host.

        Args:
            hostid: ID of the host to enable

        Returns:
            Updated host information
        """
        return await self.update_host(hostid, status=0)

    async def disable_host(self, hostid: str) -> Dict[str, Any]:
        """
        Disable monitoring for a host
        Use this to temporarily stop monitoring a host without deleting it.

        Args:
            hostid: ID of the host to disable

        Returns:
            Updated host information
        """
        return await self.update_host(hostid, status=1)

    # Item creation, update, delete
    async def create_item(self, hostid: str, name: str, key: str, item_type: int, value_type: int, **kwargs) -> Dict[str, Any]:
        """
        Create a new monitoring item
        Use this to add a new metric to collect from a host.

        Args:
            hostid: ID of the host
            name: Display name of the item
            key: Item key (e.g., "system.cpu.load[,avg1]")
            item_type: Type of item (0=Zabbix agent, 2=Zabbix trapper, 3=Simple check, etc.)
            value_type: Type of value (0=float, 1=character, 2=log, 3=unsigned int, 4=text)
            **kwargs: Additional properties like delay, history, trends, units

        Returns:
            Created item information with itemid
        """
        self._check_readonly("create_item")
        await self.ensure_authenticated()
        params = {
            "hostid": hostid,
            "name": name,
            "key_": key,
            "type": item_type,
            "value_type": value_type,
            **kwargs
        }
        return await self._make_request("item.create", params)

    async def update_item(self, itemid: str, **kwargs) -> Dict[str, Any]:
        """
        Update an existing item
        Use this to modify item properties like polling interval, value type, etc.

        Args:
            itemid: ID of the item to update
            **kwargs: Properties to update

        Returns:
            Updated item information
        """
        self._check_readonly("update_item")
        await self.ensure_authenticated()
        params = {"itemid": itemid, **kwargs}
        return await self._make_request("item.update", params)

    async def delete_item(self, itemids: List[str]) -> Dict[str, Any]:
        """
        Delete items
        Use this to remove metrics that are no longer needed.

        Args:
            itemids: List of item IDs to delete

        Returns:
            Confirmation of deletion
        """
        self._check_readonly("delete_item")
        await self.ensure_authenticated()
        return await self._make_request("item.delete", itemids)

    # Trigger creation, update, delete
    async def create_trigger(self, description: str, expression: str, priority: int = 0, **kwargs) -> Dict[str, Any]:
        """
        Create a new trigger
        Use this to define a condition that indicates a problem (e.g., high CPU usage).

        Args:
            description: Trigger description/name
            expression: Trigger expression (e.g., "{host:item.last()}>90")
            priority: Severity (0=not classified, 1=info, 2=warning, 3=average, 4=high, 5=disaster)
            **kwargs: Additional properties

        Returns:
            Created trigger information with triggerid
        """
        self._check_readonly("create_trigger")
        await self.ensure_authenticated()
        params = {"description": description, "expression": expression, "priority": priority, **kwargs}
        return await self._make_request("trigger.create", params)

    async def update_trigger(self, triggerid: str, **kwargs) -> Dict[str, Any]:
        """
        Update an existing trigger
        Use this to modify trigger conditions, severity, or other properties.

        Args:
            triggerid: ID of the trigger to update
            **kwargs: Properties to update

        Returns:
            Updated trigger information
        """
        self._check_readonly("update_trigger")
        await self.ensure_authenticated()
        params = {"triggerid": triggerid, **kwargs}
        return await self._make_request("trigger.update", params)

    async def delete_trigger(self, triggerids: List[str]) -> Dict[str, Any]:
        """
        Delete triggers
        Use this to remove triggers that are no longer needed.

        Args:
            triggerids: List of trigger IDs to delete

        Returns:
            Confirmation of deletion
        """
        self._check_readonly("delete_trigger")
        await self.ensure_authenticated()
        return await self._make_request("trigger.delete", triggerids)

    # Template methods (CRUD)
    async def create_template(self, host: str, groups: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        """
        Create a new template
        Use this to create reusable monitoring configurations.

        Args:
            host: Technical name of the template
            groups: List of template groups
            **kwargs: Additional properties

        Returns:
            Created template information with templateid
        """
        self._check_readonly("create_template")
        await self.ensure_authenticated()
        params = {"host": host, "groups": groups, **kwargs}
        return await self._make_request("template.create", params)

    async def update_template(self, templateid: str, **kwargs) -> Dict[str, Any]:
        """
        Update an existing template
        Use this to modify template properties.

        Args:
            templateid: ID of the template to update
            **kwargs: Properties to update

        Returns:
            Updated template information
        """
        self._check_readonly("update_template")
        await self.ensure_authenticated()
        params = {"templateid": templateid, **kwargs}
        return await self._make_request("template.update", params)

    async def delete_template(self, templateids: List[str]) -> Dict[str, Any]:
        """
        Delete templates
        Use this to remove templates that are no longer used.

        Args:
            templateids: List of template IDs to delete

        Returns:
            Confirmation of deletion
        """
        self._check_readonly("delete_template")
        await self.ensure_authenticated()
        return await self._make_request("template.delete", templateids)

    # Maintenance methods
    async def get_maintenances(self, output: str = "extend", **kwargs) -> List[Dict[str, Any]]:
        """
        Get maintenance periods
        Use this to see scheduled maintenance windows when monitoring is paused.

        Args:
            output: Output format
            **kwargs: Additional filters

        Returns:
            List of maintenance periods
        """
        await self.ensure_authenticated()
        params = {"output": output, **kwargs}
        return await self._make_request("maintenance.get", params)

    async def create_maintenance(self, name: str, active_since: int, active_till: int,
                                hostids: List[str] = None, groupids: List[str] = None, **kwargs) -> Dict[str, Any]:
        """
        Create a maintenance period
        Use this to schedule planned downtime when you don't want to receive alerts.

        Args:
            name: Name of the maintenance period
            active_since: Start time (Unix timestamp)
            active_till: End time (Unix timestamp)
            hostids: List of host IDs to include
            groupids: List of host group IDs to include
            **kwargs: Additional properties

        Returns:
            Created maintenance information with maintenanceid
        """
        self._check_readonly("create_maintenance")
        await self.ensure_authenticated()
        params = {
            "name": name,
            "active_since": active_since,
            "active_till": active_till,
            **kwargs
        }
        if hostids:
            params["hostids"] = hostids
        if groupids:
            params["groupids"] = groupids
        return await self._make_request("maintenance.create", params)

    async def delete_maintenance(self, maintenanceids: List[str]) -> Dict[str, Any]:
        """
        Delete maintenance periods
        Use this to remove scheduled maintenance windows.

        Args:
            maintenanceids: List of maintenance IDs to delete

        Returns:
            Confirmation of deletion
        """
        self._check_readonly("delete_maintenance")
        await self.ensure_authenticated()
        return await self._make_request("maintenance.delete", maintenanceids)

    # Action methods
    async def get_actions(self, output: str = "extend", **kwargs) -> List[Dict[str, Any]]:
        """
        Get actions (automated responses to events)
        Use this to see what automated actions are configured (notifications, commands, etc.).

        Args:
            output: Output format
            **kwargs: Additional filters

        Returns:
            List of actions
        """
        await self.ensure_authenticated()
        params = {"output": output, **kwargs}
        return await self._make_request("action.get", params)

    async def create_action(self, name: str, eventsource: int, operations: List[Dict[str, Any]], **kwargs) -> Dict[str, Any]:
        """
        Create an action
        Use this to automate responses to events (send notifications, execute commands, etc.).

        Args:
            name: Name of the action
            eventsource: Event source (0=trigger, 1=discovery, 2=auto registration, 3=internal)
            operations: List of operations to perform
            **kwargs: Additional properties like conditions, filters

        Returns:
            Created action information with actionid
        """
        self._check_readonly("create_action")
        await self.ensure_authenticated()
        params = {"name": name, "eventsource": eventsource, "operations": operations, **kwargs}
        return await self._make_request("action.create", params)

    async def delete_action(self, actionids: List[str]) -> Dict[str, Any]:
        """
        Delete actions
        Use this to remove automated response configurations.

        Args:
            actionids: List of action IDs to delete

        Returns:
            Confirmation of deletion
        """
        self._check_readonly("delete_action")
        await self.ensure_authenticated()
        return await self._make_request("action.delete", actionids)

    # User methods
    async def get_users(self, output: str = "extend", **kwargs) -> List[Dict[str, Any]]:
        """
        Get Zabbix users
        Use this to see who has access to the Zabbix system.

        Args:
            output: Output format
            **kwargs: Additional filters

        Returns:
            List of users
        """
        await self.ensure_authenticated()
        params = {"output": output, **kwargs}
        return await self._make_request("user.get", params)

    async def create_user(self, username: str, passwd: str, usrgrps: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        """
        Create a new user
        Use this to give someone access to Zabbix.

        Args:
            username: Username
            passwd: Password
            usrgrps: User groups (e.g., [{"usrgrpid": "7"}])
            **kwargs: Additional properties like name, surname, email

        Returns:
            Created user information with userid
        """
        self._check_readonly("create_user")
        await self.ensure_authenticated()
        params = {"username": username, "passwd": passwd, "usrgrps": usrgrps, **kwargs}
        return await self._make_request("user.create", params)

    async def update_user(self, userid: str, **kwargs) -> Dict[str, Any]:
        """
        Update a user
        Use this to modify user properties, password, groups, etc.

        Args:
            userid: ID of the user to update
            **kwargs: Properties to update

        Returns:
            Updated user information
        """
        self._check_readonly("update_user")
        await self.ensure_authenticated()
        params = {"userid": userid, **kwargs}
        return await self._make_request("user.update", params)

    async def delete_user(self, userids: List[str]) -> Dict[str, Any]:
        """
        Delete users
        Use this to revoke access to Zabbix.

        Args:
            userids: List of user IDs to delete

        Returns:
            Confirmation of deletion
        """
        self._check_readonly("delete_user")
        await self.ensure_authenticated()
        return await self._make_request("user.delete", userids)

    # Alert methods
    async def get_alerts(self, output: str = "extend", **kwargs) -> List[Dict[str, Any]]:
        """
        Get sent alerts/notifications
        Use this to see what notifications were sent (emails, SMS, etc.).

        Args:
            output: Output format
            **kwargs: Additional filters like time_from, time_till

        Returns:
            List of alerts
        """
        await self.ensure_authenticated()
        params = {"output": output, **kwargs}
        return await self._make_request("alert.get", params)

    # Event acknowledgment
    async def acknowledge_event(self, eventids: List[str], message: str = "", action: int = 6, **kwargs) -> Dict[str, Any]:
        """
        Acknowledge events/problems
        Use this to mark problems as acknowledged with optional message and actions.

        Args:
            eventids: List of event IDs to acknowledge
            message: Acknowledgment message
            action: Action flags (1=close, 2=ack, 4=message, 6=message+ack, etc.)
            **kwargs: Additional properties

        Returns:
            Acknowledgment confirmation
        """
        self._check_readonly("acknowledge_event")
        await self.ensure_authenticated()
        params = {"eventids": eventids, "message": message, "action": action, **kwargs}
        return await self._make_request("event.acknowledge", params)

    # Service methods (Business Services)
    async def get_services(self, output: str = "extend", **kwargs) -> List[Dict[str, Any]]:
        """
        Get IT services (business services)
        Use this to see business services and their SLA status.

        Args:
            output: Output format
            **kwargs: Additional filters

        Returns:
            List of services
        """
        await self.ensure_authenticated()
        params = {"output": output, **kwargs}
        return await self._make_request("service.get", params)

    # Trend methods
    async def get_trends(self, itemids: List[str], time_from: int = None, time_till: int = None, **kwargs) -> List[Dict[str, Any]]:
        """
        Get trend data (hourly aggregates)
        Use this to get historical trends for long-term analysis (more efficient than history).

        Args:
            itemids: List of item IDs
            time_from: Start time (Unix timestamp)
            time_till: End time (Unix timestamp)
            **kwargs: Additional parameters

        Returns:
            List of trend records
        """
        await self.ensure_authenticated()
        params = {"output": "extend", "itemids": itemids, **kwargs}
        if time_from:
            params["time_from"] = time_from
        if time_till:
            params["time_till"] = time_till
        return await self._make_request("trend.get", params)

    # Graph methods
    async def get_graphs(self, output: str = "extend", **kwargs) -> List[Dict[str, Any]]:
        """
        Get graphs
        Use this to retrieve configured graphs for visualization.

        Args:
            output: Output format
            **kwargs: Additional filters like hostids, itemids

        Returns:
            List of graphs
        """
        await self.ensure_authenticated()
        params = {"output": output, **kwargs}
        return await self._make_request("graph.get", params)

    # Script methods
    async def get_scripts(self, output: str = "extend", **kwargs) -> List[Dict[str, Any]]:
        """
        Get scripts
        Use this to see available scripts that can be executed on hosts.

        Args:
            output: Output format
            **kwargs: Additional filters

        Returns:
            List of scripts
        """
        await self.ensure_authenticated()
        params = {"output": output, **kwargs}
        return await self._make_request("script.get", params)

    async def execute_script(self, scriptid: str, hostid: str) -> Dict[str, Any]:
        """
        Execute a script on a host
        Use this to run predefined scripts on monitored hosts.

        Args:
            scriptid: ID of the script to execute
            hostid: ID of the host to execute on

        Returns:
            Script execution result
        """
        self._check_readonly("execute_script")
        await self.ensure_authenticated()
        params = {"scriptid": scriptid, "hostid": hostid}
        return await self._make_request("script.execute", params)

    # Proxy methods
    async def get_proxies(self, output: str = "extend", **kwargs) -> List[Dict[str, Any]]:
        """
        Get Zabbix proxies
        Use this to see distributed monitoring proxies.

        Args:
            output: Output format
            **kwargs: Additional filters

        Returns:
            List of proxies
        """
        await self.ensure_authenticated()
        params = {"output": output, **kwargs}
        return await self._make_request("proxy.get", params)

    # Map methods
    async def get_maps(self, output: str = "extend", **kwargs) -> List[Dict[str, Any]]:
        """
        Get network maps
        Use this to retrieve configured network topology maps.

        Args:
            output: Output format
            **kwargs: Additional filters

        Returns:
            List of maps
        """
        await self.ensure_authenticated()
        params = {"output": output, **kwargs}
        return await self._make_request("map.get", params)

    # Dashboard methods
    async def get_dashboards(self, output: str = "extend", **kwargs) -> List[Dict[str, Any]]:
        """
        Get dashboards
        Use this to see configured monitoring dashboards.

        Args:
            output: Output format
            **kwargs: Additional filters

        Returns:
            List of dashboards
        """
        await self.ensure_authenticated()
        params = {"output": output, **kwargs}
        return await self._make_request("dashboard.get", params)

    # Media type methods (notification channels)
    async def get_mediatypes(self, output: str = "extend", **kwargs) -> List[Dict[str, Any]]:
        """
        Get media types (notification channels)
        Use this to see configured notification methods (Email, SMS, Slack, etc.).

        Args:
            output: Output format
            **kwargs: Additional filters

        Returns:
            List of media types
        """
        await self.ensure_authenticated()
        params = {"output": output, **kwargs}
        return await self._make_request("mediatype.get", params)

    # Discovery rule methods
    async def get_discovery_rules(self, output: str = "extend", **kwargs) -> List[Dict[str, Any]]:
        """
        Get discovery rules (Low-Level Discovery)
        Use this to see automatic discovery rules that create items/triggers dynamically.

        Args:
            output: Output format
            **kwargs: Additional filters

        Returns:
            List of discovery rules
        """
        await self.ensure_authenticated()
        params = {"output": output, **kwargs}
        return await self._make_request("discoveryrule.get", params)

    # Network discovery methods
    async def get_dservices(self, output: str = "extend", **kwargs) -> List[Dict[str, Any]]:
        """
        Get discovered services
        Use this to see services found by network discovery.

        Args:
            output: Output format
            **kwargs: Additional filters

        Returns:
            List of discovered services
        """
        await self.ensure_authenticated()
        params = {"output": output, **kwargs}
        return await self._make_request("dservice.get", params)

    async def get_dhosts(self, output: str = "extend", **kwargs) -> List[Dict[str, Any]]:
        """
        Get discovered hosts
        Use this to see hosts found by network discovery.

        Args:
            output: Output format
            **kwargs: Additional filters

        Returns:
            List of discovered hosts
        """
        await self.ensure_authenticated()
        params = {"output": output, **kwargs}
        return await self._make_request("dhost.get", params)

    # Task methods
    async def get_tasks(self, output: str = "extend", **kwargs) -> List[Dict[str, Any]]:
        """
        Get tasks (background jobs)
        Use this to see status of background tasks like diagnostics, remote commands, etc.

        Args:
            output: Output format
            **kwargs: Additional filters

        Returns:
            List of tasks
        """
        await self.ensure_authenticated()
        params = {"output": output, **kwargs}
        return await self._make_request("task.get", params)

    # Value mapping methods
    async def get_valuemaps(self, output: str = "extend", **kwargs) -> List[Dict[str, Any]]:
        """
        Get value mappings
        Use this to see how numeric values are mapped to text (e.g., 0='Down', 1='Up').

        Args:
            output: Output format
            **kwargs: Additional filters

        Returns:
            List of value maps
        """
        await self.ensure_authenticated()
        params = {"output": output, **kwargs}
        return await self._make_request("valuemap.get", params)

    # Web scenario methods (web monitoring)
    async def get_web_scenarios(self, output: str = "extend", **kwargs) -> List[Dict[str, Any]]:
        """
        Get web monitoring scenarios
        Use this to see configured website/web application monitoring.

        Args:
            output: Output format
            **kwargs: Additional filters

        Returns:
            List of web scenarios
        """
        await self.ensure_authenticated()
        params = {"output": output, **kwargs}
        return await self._make_request("httptest.get", params)

    # Report methods
    async def get_report_status(self, hostids: List[str] = None) -> Dict[str, Any]:
        """
        Get host availability report
        Use this to get statistics on host availability.

        Args:
            hostids: List of host IDs to include

        Returns:
            Availability statistics
        """
        await self.ensure_authenticated()
        params = {}
        if hostids:
            params["hostids"] = hostids
        return await self._make_request("host.get", {**params, "output": ["hostid", "host", "available"]})

    # Generic method for any Zabbix API call
    async def call(self, method: str, params: Dict[str, Any] = None) -> Any:
        """
        Make a generic Zabbix API call
        Use this for any Zabbix API method not explicitly implemented.

        Args:
            method: Zabbix API method name (e.g., 'host.get', 'item.create')
            params: Method parameters

        Returns:
            API response result
        """
        # Check if the method is a write operation
        write_operations = ['.create', '.update', '.delete', '.execute', 'acknowledge']
        if any(op in method.lower() for op in write_operations):
            self._check_readonly(f"call({method})")
        
        if method != "apiinfo.version" and method != "user.login":
            await self.ensure_authenticated()
        return await self._make_request(method, params)
