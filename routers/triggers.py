"""
Trigger management endpoints - Alert conditions
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import Optional
from zabbix_client import ZabbixClient, ZabbixAPIError, ReadOnlyModeError
from config import settings

router = APIRouter(prefix="/api/triggers", tags=["Triggers"])


def get_zabbix_client() -> ZabbixClient:
    """Get the global Zabbix client instance"""
    from main import zabbix_client
    if zabbix_client is None:
        raise HTTPException(status_code=503, detail="Zabbix client not initialized")
    return zabbix_client


class TriggerCreateRequest(BaseModel):
    """Request to create a trigger"""
    description: str = Field(..., description="Trigger name/description")
    expression: str = Field(..., description="Trigger expression (e.g., '{host:item.last()}>90')")
    priority: int = Field(0, ge=0, le=5, description="Severity: 0=not classified, 1=info, 2=warning, 3=average, 4=high, 5=disaster")


@router.get("", summary="List triggers (alert conditions)")
async def get_triggers(
    hostids: Optional[str] = Query(None, description="Comma-separated host IDs"),
    active_only: bool = Query(False, description="Show only active (problem) triggers"),
    min_severity: int = Query(0, ge=0, le=5, description="Minimum severity (0-5)"),
    client: ZabbixClient = Depends(get_zabbix_client)
):
    """
    **Get triggers (alert conditions)**

    Use this to:
    - See configured alert conditions
    - Find active problems (use active_only=true)
    - Filter by severity level

    Severity levels:
    - 0 = Not classified
    - 1 = Information
    - 2 = Warning
    - 3 = Average
    - 4 = High
    - 5 = Disaster

    Active triggers indicate current problems that need attention.
    """
    try:
        if active_only:
            triggers = await client.get_active_triggers(min_severity=min_severity)
        else:
            params = {}
            if hostids:
                params["hostids"] = hostids.split(",")
            if min_severity > 0:
                params["min_severity"] = min_severity
            triggers = await client.get_triggers(**params)

        return {"triggers": triggers, "count": len(triggers)}
    except ZabbixAPIError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", summary="Create a new trigger", include_in_schema=not settings.zabbix_readonly)
async def create_trigger(
    request: TriggerCreateRequest,
    client: ZabbixClient = Depends(get_zabbix_client)
):
    """
    **Create a new trigger (alert condition)**

    Use this to:
    - Define conditions that indicate problems
    - Set up alerts for specific thresholds
    - Create complex monitoring rules

    Example expressions:
    - {host:item.last()}>90 - Last value exceeds 90
    - {host:item.avg(5m)}>80 - 5-minute average exceeds 80
    - {host:item.nodata(10m)}=1 - No data received for 10 minutes
    """
    try:
        result = await client.create_trigger(
            description=request.description,
            expression=request.expression,
            priority=request.priority
        )
        return {"success": True, "triggerid": result["triggerids"][0], "message": "Trigger created successfully"}
    except ZabbixAPIError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{triggerid}", summary="Delete a trigger", include_in_schema=not settings.zabbix_readonly)
async def delete_trigger(
    triggerid: str,
    client: ZabbixClient = Depends(get_zabbix_client)
):
    """
    **Delete a trigger**

    Use this to:
    - Remove alert conditions that are no longer needed
    - Clean up obsolete monitoring rules
    """
    try:
        await client.delete_trigger([triggerid])
        return {"success": True, "message": "Trigger deleted successfully"}
    except ZabbixAPIError as e:
        raise HTTPException(status_code=500, detail=str(e))
