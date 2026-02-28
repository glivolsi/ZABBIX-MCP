"""
Problem management endpoints - Active issues and acknowledgments
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import Optional, List
from zabbix_client import ZabbixClient, ZabbixAPIError, ReadOnlyModeError
from config import settings

router = APIRouter(prefix="/api/problems", tags=["Problems"])


def get_zabbix_client() -> ZabbixClient:
    """Get the global Zabbix client instance"""
    from main import zabbix_client
    if zabbix_client is None:
        raise HTTPException(status_code=503, detail="Zabbix client not initialized")
    return zabbix_client


class EventAcknowledgeRequest(BaseModel):
    """Request to acknowledge events"""
    eventids: List[str] = Field(..., description="List of event IDs to acknowledge")
    message: Optional[str] = Field("", description="Acknowledgment message")
    action: int = Field(6, description="Action: 1=close, 2=ack, 4=message, 6=message+ack")


@router.get("", summary="Get current problems/issues")
async def get_problems(
    hostids: Optional[str] = Query(None, description="Comma-separated host IDs"),
    severities: Optional[str] = Query(None, description="Comma-separated severity levels (0-5)"),
    client: ZabbixClient = Depends(get_zabbix_client)
):
    """
    **Get current problems (active issues)**

    Use this to:
    - See what's currently wrong in your infrastructure
    - Monitor active alerts and incidents
    - Filter problems by host or severity
    - Check what needs immediate attention

    This is the primary endpoint for checking system health - it shows only currently active problems.
    """
    try:
        params = {}
        if hostids:
            params["hostids"] = hostids.split(",")
        if severities:
            params["severities"] = [int(s) for s in severities.split(",")]

        problems = await client.get_problems(**params)
        return {"problems": problems, "count": len(problems)}
    except ZabbixAPIError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/acknowledge", summary="Acknowledge problems", include_in_schema=not settings.zabbix_readonly)
async def acknowledge_problems(
    request: EventAcknowledgeRequest,
    client: ZabbixClient = Depends(get_zabbix_client)
):
    """
    **Acknowledge problems**

    Use this to:
    - Mark problems as acknowledged (someone is working on them)
    - Add comments to problems
    - Close resolved problems
    - Communicate problem status to the team

    Action flags:
    - 1 = Close problem
    - 2 = Acknowledge problem
    - 4 = Add message
    - 6 = Acknowledge + add message (recommended)
    """
    try:
        result = await client.acknowledge_event(
            eventids=request.eventids,
            message=request.message,
            action=request.action
        )
        return {"success": True, "message": f"Acknowledged {len(request.eventids)} events"}
    except ZabbixAPIError as e:
        raise HTTPException(status_code=500, detail=str(e))
