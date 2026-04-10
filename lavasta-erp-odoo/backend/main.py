import os
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from pydantic import BaseModel, Field

from odoo_client import OdooClient, OdooConnectionError

app = FastAPI(title="Lavasta ERP Backend API", version="1.0.0")
odoo_client = OdooClient()


def verify_api_token(x_api_token: str = Header(..., alias="X-API-TOKEN")) -> None:
    """Simple header-based auth for all API endpoints."""
    expected_token = os.getenv("API_TOKEN", "")
    if not expected_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API_TOKEN is not configured on backend service.",
        )
    if x_api_token != expected_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API token.",
        )


def _odoo_safe_execute(model: str, method: str, args: list[Any], kwargs: dict[str, Any] | None = None) -> Any:
    """Wrap XML-RPC execution and convert low-level errors to API-friendly errors."""
    try:
        return odoo_client.execute_kw(model=model, method=method, args=args, kwargs=kwargs or {})
    except OdooConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Odoo is unavailable: {exc}",
        ) from exc
    except Exception as exc:  # Defensive fallback for unexpected RPC errors.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Odoo RPC error: {exc}",
        ) from exc


class OrderCreateRequest(BaseModel):
    product_id: int = Field(..., gt=0)
    product_qty: float = Field(..., gt=0)
    bom_id: int = Field(..., gt=0)


class OrderCreateResponse(BaseModel):
    id: int


class EmployeeByPhoneResponse(BaseModel):
    id: int
    name: str
    department_id: int | None


class WorkHistoryItem(BaseModel):
    id: int
    datetime: str | None
    operation: str | None
    order: str | None
    seconds: int | None
    status: str | None


@app.post(
    "/api/v1/orders/create",
    response_model=OrderCreateResponse,
    dependencies=[Depends(verify_api_token)],
)
def create_order(payload: OrderCreateRequest) -> OrderCreateResponse:
    values = {
        "product_id": payload.product_id,
        "product_qty": payload.product_qty,
        "bom_id": payload.bom_id,
    }
    created_id = _odoo_safe_execute("mrp.production", "create", [values])
    return OrderCreateResponse(id=int(created_id))


@app.get(
    "/api/v1/employees/by-phone/{phone}",
    response_model=EmployeeByPhoneResponse,
    dependencies=[Depends(verify_api_token)],
)
def get_employee_by_phone(phone: str) -> EmployeeByPhoneResponse:
    domain = ["|", ("mobile_phone", "ilike", phone), ("work_phone", "ilike", phone)]
    records = _odoo_safe_execute(
        "hr.employee",
        "search_read",
        [domain],
        {"fields": ["id", "name", "department_id"], "limit": 1},
    )

    if not records:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee with phone '{phone}' not found.",
        )

    employee = records[0]
    department_raw = employee.get("department_id")
    department_id = department_raw[0] if isinstance(department_raw, list) and department_raw else None

    return EmployeeByPhoneResponse(
        id=employee["id"],
        name=employee.get("name", ""),
        department_id=department_id,
    )


@app.get(
    "/api/v1/employees/{employee_id}/work-history",
    response_model=list[WorkHistoryItem],
    dependencies=[Depends(verify_api_token)],
)
def get_work_history(
    employee_id: int,
    date_start: str | None = Query(default=None, description="YYYY-MM-DD"),
    date_end: str | None = Query(default=None, description="YYYY-MM-DD"),
) -> list[WorkHistoryItem]:
    domain: list[Any] = [("employee_id", "=", employee_id)]
    if date_start:
        domain.append(("datetime", ">=", f"{date_start} 00:00:00"))
    if date_end:
        domain.append(("datetime", "<=", f"{date_end} 23:59:59"))

    records = _odoo_safe_execute(
        "employee.work.history",
        "search_read",
        [domain],
        {
            "fields": ["id", "datetime", "operation_id", "order_id", "seconds"],
            "order": "datetime desc",
        },
    )

    result: list[WorkHistoryItem] = []
    for rec in records:
        operation_raw = rec.get("operation_id")
        order_raw = rec.get("order_id")

        result.append(
            WorkHistoryItem(
                id=rec["id"],
                datetime=rec.get("datetime"),
                operation=operation_raw[1] if isinstance(operation_raw, list) and len(operation_raw) > 1 else None,
                order=order_raw[1] if isinstance(order_raw, list) and len(order_raw) > 1 else None,
                seconds=rec.get("seconds"),
                status=rec.get("status"),
            )
        )

    return result
