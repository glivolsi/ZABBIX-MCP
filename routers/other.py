"""
Remaining endpoints - Events, Groups, Templates, Maintenance, Users, Monitoring, Automation, Visualization, Discovery, Generic
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from zabbix_client import ZabbixClient, ZabbixAPIError, ReadOnlyModeError
from config import settings

# Create multiple routers for different categories
events_router = APIRouter(prefix="/api/events", tags=["Events"])
groups_router = APIRouter(prefix="/api/hostgroups", tags=["Host Groups"])
templates_router = APIRouter(prefix="/api/templates", tags=["Templates"])
maintenance_router = APIRouter(prefix="/api/maintenances", tags=["Maintenance"])
users_router = APIRouter(prefix="/api/users", tags=["Users"])
alerts_router = APIRouter(prefix="/api/alerts", tags=["Alerts"])
actions_router = APIRouter(prefix="/api/actions", tags=["Actions"])
services_router = APIRouter(prefix="/api/services", tags=["Services"])
graphs_router = APIRouter(prefix="/api/graphs", tags=["Graphs"])
scripts_router = APIRouter(prefix="/api/scripts", tags=["Scripts"])
proxies_router = APIRouter(prefix="/api/proxies", tags=["Proxies"])
maps_router = APIRouter(prefix="/api/maps", tags=["Maps"])
dashboards_router = APIRouter(prefix="/api/dashboards", tags=["Dashboards"])
discovery_router = APIRouter(prefix="/api/discovery", tags=["Discovery"])
generic_router = APIRouter(prefix="/api", tags=["Generic"])


def get_zabbix_client() -> ZabbixClient:
    """Get the global Zabbix client instance"""
    from main import zabbix_client
    if zabbix_client is None:
        raise HTTPException(status_code=503, detail="Zabbix client not initialized")
    return zabbix_client


# Models
class MaintenanceCreateRequest(BaseModel):
    """Request to create a maintenance period"""
    name: str = Field(..., description="Name of the maintenance period")
    active_since: int = Field(..., description="Start time (Unix timestamp)")
    active_till: int = Field(..., description="End time (Unix timestamp)")
    hostids: Optional[List[str]] = Field(None, description="Host IDs to include in maintenance")
    groupids: Optional[List[str]] = Field(None, description="Host group IDs to include in maintenance")


class ZabbixGenericRequest(BaseModel):
    """Generic Zabbix API request"""
    method: str = Field(..., description="Zabbix API method name (e.g., 'host.get', 'item.get')")
    params: Optional[Dict[str, Any]] = Field(default={}, description="Method parameters")


# Events endpoints
@events_router.get("", summary="Get event log entries")
async def get_events(
    hostids: Optional[str] = Query(None, description="Comma-separated host IDs"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of events"),
    client: ZabbixClient = Depends(get_zabbix_client)
):
    """Get events from Zabbix event log"""
    try:
        params = {}
        if hostids:
            params["hostids"] = hostids.split(",")
        events = await client.get_events(limit=limit, **params)
        return {"events": events, "count": len(events)}
    except ZabbixAPIError as e:
        raise HTTPException(status_code=500, detail=str(e))


# Host Groups endpoints
@groups_router.get("", summary="List host groups")
async def get_hostgroups(client: ZabbixClient = Depends(get_zabbix_client)):
    """Get host groups (organizational units)"""
    try:
        groups = await client.get_hostgroups()
        return {"hostgroups": groups, "count": len(groups)}
    except ZabbixAPIError as e:
        raise HTTPException(status_code=500, detail=str(e))


@groups_router.post("", summary="Create a host group", include_in_schema=not settings.zabbix_readonly)
async def create_hostgroup(
    name: str = Query(..., description="Name of the host group"),
    client: ZabbixClient = Depends(get_zabbix_client)
):
    """Create a new host group"""
    try:
        result = await client.create_hostgroup(name)
        return {"success": True, "groupid": result["groupids"][0], "message": "Host group created successfully"}
    except ZabbixAPIError as e:
        raise HTTPException(status_code=500, detail=str(e))


@groups_router.delete("/{groupid}", summary="Delete a host group", include_in_schema=not settings.zabbix_readonly)
async def delete_hostgroup(
    groupid: str,
    client: ZabbixClient = Depends(get_zabbix_client)
):
    """Delete a host group"""
    try:
        await client.delete_hostgroup([groupid])
        return {"success": True, "message": "Host group deleted successfully"}
    except ZabbixAPIError as e:
        raise HTTPException(status_code=500, detail=str(e))


# Templates endpoints
@templates_router.get("", summary="List monitoring templates")
async def get_templates(client: ZabbixClient = Depends(get_zabbix_client)):
    """Get monitoring templates (reusable configurations)"""
    try:
        templates = await client.get_templates()
        return {"templates": templates, "count": len(templates)}
    except ZabbixAPIError as e:
        raise HTTPException(status_code=500, detail=str(e))


@templates_router.post("", summary="Create a template", include_in_schema=not settings.zabbix_readonly)
async def create_template(
    name: str = Query(..., description="Template name"),
    groups: str = Query(..., description="Comma-separated group IDs"),
    client: ZabbixClient = Depends(get_zabbix_client)
):
    """Create a new monitoring template"""
    try:
        group_list = [{"groupid": gid} for gid in groups.split(",")]
        result = await client.create_template(host=name, groups=group_list)
        return {"success": True, "templateid": result["templateids"][0], "message": "Template created successfully"}
    except ZabbixAPIError as e:
        raise HTTPException(status_code=500, detail=str(e))


@templates_router.delete("/{templateid}", summary="Delete a template", include_in_schema=not settings.zabbix_readonly)
async def delete_template(
    templateid: str,
    client: ZabbixClient = Depends(get_zabbix_client)
):
    """Delete a monitoring template"""
    try:
        await client.delete_template([templateid])
        return {"success": True, "message": "Template deleted successfully"}
    except ZabbixAPIError as e:
        raise HTTPException(status_code=500, detail=str(e))


# Maintenance endpoints
@maintenance_router.get("", summary="List maintenance periods")
async def get_maintenances(client: ZabbixClient = Depends(get_zabbix_client)):
    """Get maintenance periods (scheduled downtime)"""
    try:
        maintenances = await client.get_maintenances()
        return {"maintenances": maintenances, "count": len(maintenances)}
    except ZabbixAPIError as e:
        raise HTTPException(status_code=500, detail=str(e))


@maintenance_router.post("", summary="Create maintenance period", include_in_schema=not settings.zabbix_readonly)
async def create_maintenance(
    request: MaintenanceCreateRequest,
    client: ZabbixClient = Depends(get_zabbix_client)
):
    """Create a maintenance period (scheduled downtime)"""
    try:
        result = await client.create_maintenance(
            name=request.name,
            active_since=request.active_since,
            active_till=request.active_till,
            hostids=request.hostids,
            groupids=request.groupids
        )
        return {"success": True, "maintenanceid": result["maintenanceids"][0], "message": "Maintenance created successfully"}
    except ZabbixAPIError as e:
        raise HTTPException(status_code=500, detail=str(e))


@maintenance_router.delete("/{maintenanceid}", summary="Delete maintenance period", include_in_schema=not settings.zabbix_readonly)
async def delete_maintenance(
    maintenanceid: str,
    client: ZabbixClient = Depends(get_zabbix_client)
):
    """Delete a maintenance period"""
    try:
        await client.delete_maintenance([maintenanceid])
        return {"success": True, "message": "Maintenance deleted successfully"}
    except ZabbixAPIError as e:
        raise HTTPException(status_code=500, detail=str(e))


# Users endpoints
@users_router.get("", summary="List Zabbix users")
async def get_users(client: ZabbixClient = Depends(get_zabbix_client)):
    """Get Zabbix users"""
    try:
        users = await client.get_users()
        return {"users": users, "count": len(users)}
    except ZabbixAPIError as e:
        raise HTTPException(status_code=500, detail=str(e))


# Alerts endpoints
@alerts_router.get("", summary="Get sent alerts/notifications")
async def get_alerts(
    time_from: Optional[int] = Query(None, description="Start time (Unix timestamp)"),
    time_till: Optional[int] = Query(None, description="End time (Unix timestamp)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of alerts"),
    client: ZabbixClient = Depends(get_zabbix_client)
):
    """Get sent alerts and notifications"""
    try:
        params = {"sortfield": "clock", "sortorder": "DESC", "limit": limit}
        if time_from:
            params["time_from"] = time_from
        if time_till:
            params["time_till"] = time_till
        alerts = await client.get_alerts(**params)
        return {"alerts": alerts, "count": len(alerts)}
    except ZabbixAPIError as e:
        raise HTTPException(status_code=500, detail=str(e))


# Actions endpoints
@actions_router.get("", summary="List automated actions")
async def get_actions(client: ZabbixClient = Depends(get_zabbix_client)):
    """Get actions (automated responses)"""
    try:
        actions = await client.get_actions()
        return {"actions": actions, "count": len(actions)}
    except ZabbixAPIError as e:
        raise HTTPException(status_code=500, detail=str(e))


# Services endpoints
@services_router.get("", summary="Get IT/Business services")
async def get_services(client: ZabbixClient = Depends(get_zabbix_client)):
    """Get IT/Business services (SLA monitoring)"""
    try:
        services = await client.get_services()
        return {"services": services, "count": len(services)}
    except ZabbixAPIError as e:
        raise HTTPException(status_code=500, detail=str(e))


# Graphs endpoints
@graphs_router.get("", summary="Get configured graphs")
async def get_graphs(
    hostids: Optional[str] = Query(None, description="Comma-separated host IDs"),
    client: ZabbixClient = Depends(get_zabbix_client)
):
    """Get configured graphs for visualization"""
    try:
        params = {}
        if hostids:
            params["hostids"] = hostids.split(",")
        graphs = await client.get_graphs(**params)
        return {"graphs": graphs, "count": len(graphs)}
    except ZabbixAPIError as e:
        raise HTTPException(status_code=500, detail=str(e))


# Scripts endpoints
@scripts_router.get("", summary="List executable scripts")
async def get_scripts(client: ZabbixClient = Depends(get_zabbix_client)):
    """Get scripts that can be executed on hosts"""
    try:
        scripts = await client.get_scripts()
        return {"scripts": scripts, "count": len(scripts)}
    except ZabbixAPIError as e:
        raise HTTPException(status_code=500, detail=str(e))


@scripts_router.post("/{scriptid}/execute", summary="Execute a script on a host", include_in_schema=not settings.zabbix_readonly)
async def execute_script(
    scriptid: str,
    hostid: str = Query(..., description="ID of the host to execute script on"),
    client: ZabbixClient = Depends(get_zabbix_client)
):
    """Execute a remote script on a host"""
    try:
        result = await client.execute_script(scriptid, hostid)
        return {"success": True, "result": result, "message": "Script executed successfully"}
    except ZabbixAPIError as e:
        raise HTTPException(status_code=500, detail=str(e))


# Proxies endpoints
@proxies_router.get("", summary="List Zabbix proxies")
async def get_proxies(client: ZabbixClient = Depends(get_zabbix_client)):
    """Get Zabbix proxies (distributed monitoring)"""
    try:
        proxies = await client.get_proxies()
        return {"proxies": proxies, "count": len(proxies)}
    except ZabbixAPIError as e:
        raise HTTPException(status_code=500, detail=str(e))


# Maps endpoints
@maps_router.get("", summary="Get network maps")
async def get_maps(client: ZabbixClient = Depends(get_zabbix_client)):
    """Get network maps (topology visualization)"""
    try:
        maps = await client.get_maps()
        return {"maps": maps, "count": len(maps)}
    except ZabbixAPIError as e:
        raise HTTPException(status_code=500, detail=str(e))


# Dashboards endpoints
@dashboards_router.get("", summary="Get dashboards")
async def get_dashboards(client: ZabbixClient = Depends(get_zabbix_client)):
    """Get configured monitoring dashboards"""
    try:
        dashboards = await client.get_dashboards()
        return {"dashboards": dashboards, "count": len(dashboards)}
    except ZabbixAPIError as e:
        raise HTTPException(status_code=500, detail=str(e))


# Discovery endpoints
@discovery_router.get("/rules", summary="Get Low-Level Discovery rules")
async def get_discovery_rules(
    hostids: Optional[str] = Query(None, description="Comma-separated host IDs"),
    client: ZabbixClient = Depends(get_zabbix_client)
):
    """Get Low-Level Discovery (LLD) rules"""
    try:
        params = {}
        if hostids:
            params["hostids"] = hostids.split(",")
        rules = await client.get_discovery_rules(**params)
        return {"discovery_rules": rules, "count": len(rules)}
    except ZabbixAPIError as e:
        raise HTTPException(status_code=500, detail=str(e))


@discovery_router.get("/hosts", summary="Get discovered hosts")
async def get_discovered_hosts(client: ZabbixClient = Depends(get_zabbix_client)):
    """Get hosts discovered by network discovery"""
    try:
        dhosts = await client.get_dhosts()
        return {"discovered_hosts": dhosts, "count": len(dhosts)}
    except ZabbixAPIError as e:
        raise HTTPException(status_code=500, detail=str(e))


@discovery_router.get("/services", summary="Get discovered services")
async def get_discovered_services(client: ZabbixClient = Depends(get_zabbix_client)):
    """Get services discovered by network discovery"""
    try:
        dservices = await client.get_dservices()
        return {"discovered_services": dservices, "count": len(dservices)}
    except ZabbixAPIError as e:
        raise HTTPException(status_code=500, detail=str(e))


# Generic API call endpoint
@generic_router.post("/call", summary="Make any Zabbix API call", include_in_schema=not settings.zabbix_readonly)
async def call_zabbix_api(
    request: ZabbixGenericRequest,
    client: ZabbixClient = Depends(get_zabbix_client)
):
    """
    Make a generic Zabbix API call (for advanced/uncommon operations)

    Use this ONLY when you need a Zabbix API method not covered by other endpoints.
    Prefer using specific endpoints as they are more user-friendly and better documented.
    """
    try:
        result = await client.call(request.method, request.params)
        return {"result": result}
    except ZabbixAPIError as e:
        raise HTTPException(status_code=500, detail=str(e))


# Export all routers
all_routers = [
    events_router,
    groups_router,
    templates_router,
    maintenance_router,
    users_router,
    alerts_router,
    actions_router,
    services_router,
    graphs_router,
    scripts_router,
    proxies_router,
    maps_router,
    dashboards_router,
    discovery_router,
    generic_router
]
