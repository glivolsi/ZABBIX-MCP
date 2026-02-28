"""
Host management endpoints - CRUD operations for hosts
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from zabbix_client import ZabbixClient, ZabbixAPIError, ReadOnlyModeError
from config import settings

router = APIRouter(prefix="/api/hosts", tags=["Hosts"])


def get_zabbix_client() -> ZabbixClient:
    """Get the global Zabbix client instance"""
    from main import zabbix_client
    if zabbix_client is None:
        raise HTTPException(status_code=503, detail="Zabbix client not initialized")
    return zabbix_client


class HostCreateRequest(BaseModel):
    """Request to create a new host"""
    host: str = Field(..., description="Technical name of the host (hostname)")
    groups: List[Dict[str, str]] = Field(..., description="Host groups, e.g., [{'groupid': '2'}]")
    interfaces: List[Dict[str, Any]] = Field(..., description="Network interfaces configuration")
    templates: Optional[List[Dict[str, str]]] = Field(None, description="Templates to link, e.g., [{'templateid': '10001'}]")


class HostUpdateRequest(BaseModel):
    """Request to update a host"""
    hostid: str = Field(..., description="ID of the host to update")
    properties: Dict[str, Any] = Field(..., description="Properties to update")


@router.get("", summary="List all monitored hosts")
async def get_hosts(
    name: Optional[str] = Query(None, description="Filter by host name"),
    groupids: Optional[str] = Query(None, description="Comma-separated host group IDs"),
    client: ZabbixClient = Depends(get_zabbix_client)
):
    """
    **Get list of monitored hosts**

    Use this endpoint to:
    - Get all hosts being monitored by Zabbix
    - Find a specific host by name
    - Filter hosts by group membership
    - Check host configuration and status

    Returns detailed information about each host including interfaces, groups, and status.
    """
    try:
        params = {}
        if name:
            params["filter"] = {"host": name}
        if groupids:
            params["groupids"] = groupids.split(",")

        hosts = await client.get_hosts(**params)
        return {"hosts": hosts, "count": len(hosts)}
    except ZabbixAPIError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{hostname}", summary="Get specific host by name")
async def get_host_by_name(
    hostname: str,
    client: ZabbixClient = Depends(get_zabbix_client)
):
    """
    **Get a specific host by its hostname**

    Use this when you need to:
    - Find details about a specific server or device
    - Get the host ID for other operations
    - Check if a host exists in Zabbix
    """
    try:
        host = await client.get_host_by_name(hostname)
        if not host:
            raise HTTPException(status_code=404, detail=f"Host '{hostname}' not found")
        return {"host": host}
    except ZabbixAPIError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", summary="Create a new host", include_in_schema=not settings.zabbix_readonly)
async def create_host(
    request: HostCreateRequest,
    client: ZabbixClient = Depends(get_zabbix_client)
):
    """
    **Create a new host in Zabbix**

    Use this to:
    - Add a new server, device, or application to monitor
    - Configure monitoring for new infrastructure
    - Set up agents, SNMP devices, or JMX monitoring

    Requires: host name, at least one group, and at least one interface.
    """
    try:
        result = await client.create_host(
            host=request.host,
            groups=request.groups,
            interfaces=request.interfaces,
            templates=request.templates or []
        )
        return {"success": True, "hostid": result["hostids"][0], "message": "Host created successfully"}
    except ZabbixAPIError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{hostid}", summary="Update a host", include_in_schema=not settings.zabbix_readonly)
async def update_host(
    hostid: str,
    request: HostUpdateRequest,
    client: ZabbixClient = Depends(get_zabbix_client)
):
    """
    **Update an existing host**

    Use this to:
    - Modify host properties (name, groups, templates)
    - Update interface configuration
    - Change monitoring parameters
    """
    try:
        result = await client.update_host(hostid, **request.properties)
        return {"success": True, "message": "Host updated successfully"}
    except ZabbixAPIError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{hostid}", summary="Delete a host", include_in_schema=not settings.zabbix_readonly)
async def delete_host(
    hostid: str,
    client: ZabbixClient = Depends(get_zabbix_client)
):
    """
    **Delete a host from Zabbix**

    Use this to:
    - Remove hosts that are no longer monitored
    - Clean up decommissioned infrastructure

    Warning: This will delete all associated items, triggers, and historical data.
    """
    try:
        result = await client.delete_host([hostid])
        return {"success": True, "message": "Host deleted successfully"}
    except ZabbixAPIError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{hostid}/enable", summary="Enable host monitoring", include_in_schema=not settings.zabbix_readonly)
async def enable_host(
    hostid: str,
    client: ZabbixClient = Depends(get_zabbix_client)
):
    """
    **Enable monitoring for a host**

    Use this to:
    - Resume monitoring a previously disabled host
    - Start collecting data after maintenance
    """
    try:
        await client.enable_host(hostid)
        return {"success": True, "message": "Host enabled successfully"}
    except ZabbixAPIError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{hostid}/disable", summary="Disable host monitoring", include_in_schema=not settings.zabbix_readonly)
async def disable_host(
    hostid: str,
    client: ZabbixClient = Depends(get_zabbix_client)
):
    """
    **Disable monitoring for a host**

    Use this to:
    - Temporarily stop monitoring without deleting the host
    - Pause data collection during maintenance
    - Reduce monitoring load
    """
    try:
        await client.disable_host(hostid)
        return {"success": True, "message": "Host disabled successfully"}
    except ZabbixAPIError as e:
        raise HTTPException(status_code=500, detail=str(e))
