import os
from typing import Literal
from typing import Any
from datetime import datetime

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator

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


class OperationDirectoryItem(BaseModel):
    id: int
    name: str
    department_id: int | None


class WorkOrderItem(BaseModel):
    id: int
    name: str
    production_id: int | None
    state: str | None
    duration: float | None


class DepartmentResponse(BaseModel):
    id: int
    name: str


class CreateWorkOrderRequest(BaseModel):
    production_id: int = Field(..., gt=0)
    name: str = Field(..., min_length=1)
    workcenter_id: int = Field(..., gt=0)
    duration_expected: float | None = Field(default=None, ge=0)


class CreateWorkOrderResponse(BaseModel):
    id: int


class AttendanceTodayResponse(BaseModel):
    check_in: str | None
    check_out: str | None
    lavasta_attendance_status: str | None


class AttendanceActionRequest(BaseModel):
    employee_id: int = Field(..., gt=0)
    action: Literal["start", "end"]
    manual_time: str | None = Field(
        default=None,
        description="Manual datetime in format YYYY-MM-DD HH:MM:SS",
    )
    status: str | None = Field(
        default=None,
        description="Optional client field, backend calculates final status automatically.",
    )

    @field_validator("manual_time")
    @classmethod
    def validate_manual_time(cls, value: str | None) -> str | None:
        if value is None:
            return value
        try:
            datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        except ValueError as exc:
            raise ValueError("manual_time must be in format YYYY-MM-DD HH:MM:SS") from exc
        return value


class AttendanceActionResponse(BaseModel):
    attendance_id: int
    action: Literal["start", "end"]
    message: str


@app.post(
    "/api/v1/orders/create",
    response_model=OrderCreateResponse,
    dependencies=[Depends(verify_api_token)],
    summary="Create manufacturing order in Odoo",
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
    summary="Get employee by phone number",
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
    summary="Get employee work history",
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


@app.get(
    "/api/v1/employees/{employee_id}/attendance/today",
    response_model=AttendanceTodayResponse,
    dependencies=[Depends(verify_api_token)],
    summary="Get today's attendance state for employee",
)
def get_today_attendance(employee_id: int) -> AttendanceTodayResponse:
    try:
        records = odoo_client.get_today_attendance(employee_id=employee_id)
    except OdooConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Odoo is unavailable: {exc}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Odoo RPC error: {exc}",
        ) from exc

    if not records:
        return AttendanceTodayResponse(
            check_in=None,
            check_out=None,
            lavasta_attendance_status=None,
        )

    latest = records[0]
    return AttendanceTodayResponse(
        check_in=latest.get("check_in"),
        check_out=latest.get("check_out"),
        lavasta_attendance_status=latest.get("lavasta_attendance_status"),
    )


@app.post(
    "/api/v1/employees/attendance",
    response_model=AttendanceActionResponse,
    dependencies=[Depends(verify_api_token)],
    summary="Start or end employee attendance shift",
)
def attendance_action(payload: AttendanceActionRequest) -> AttendanceActionResponse:
    # Manual time means retrospective correction, so it requires confirmation later.
    resolved_status: Literal["confirmed", "unconfirmed"] = (
        "unconfirmed" if payload.manual_time else "confirmed"
    )
    try:
        attendance_id = odoo_client.attendance_action(
            employee_id=payload.employee_id,
            action=payload.action,
            status=resolved_status,
            manual_time=payload.manual_time,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except OdooConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Odoo is unavailable: {exc}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Odoo RPC error: {exc}",
        ) from exc

    return AttendanceActionResponse(
        attendance_id=attendance_id,
        action=payload.action,
        message=f"Attendance action '{payload.action}' completed successfully.",
    )


@app.get(
    "/api/v1/operations/directory",
    response_model=list[OperationDirectoryItem],
    dependencies=[Depends(verify_api_token)],
    summary="Get operation directory by department",
)
def get_operations_directory(department_id: int = Query(..., gt=0)) -> list[OperationDirectoryItem]:
    records = _odoo_safe_execute(
        "lavasta.operation.directory",
        "search_read",
        [[("department_id", "=", department_id)]],
        {"fields": ["id", "name", "department_id"], "order": "id asc"},
    )

    result: list[OperationDirectoryItem] = []
    for rec in records:
        department_raw = rec.get("department_id")
        result.append(
            OperationDirectoryItem(
                id=rec["id"],
                name=rec.get("name", ""),
                department_id=department_raw[0] if isinstance(department_raw, list) and department_raw else None,
            )
        )
    return result


@app.get(
    "/api/v1/orders/operations/list",
    response_model=list[dict[str, Any]],
    dependencies=[Depends(verify_api_token)],
    summary="Get work orders for multiple production orders",
    description="Fetch work orders by production order IDs with optional department filter and detail level.",
)
def get_order_operations(
    order_ids: list[int] = Query(..., description="List of Production Order IDs"),
    department_id: int | None = Query(default=None, gt=0),
    full_details: bool = Query(default=False, description="If true, returns all fields from Odoo"),
) -> list[dict[str, Any]]:
    domain: list[Any] = [("production_id", "in", order_ids)]

    if department_id is not None:
        directory_records = _odoo_safe_execute(
            "lavasta.operation.directory",
            "search_read",
            [[("department_id", "=", department_id)]],
            {"fields": ["name"]},
        )
        valid_names = [rec.get("name") for rec in directory_records if rec.get("name")]
        if not valid_names:
            return []
        domain.append(("name", "in", valid_names))

    records = _odoo_safe_execute(
        "mrp.workorder",
        "search_read",
        [domain],
        {
            "fields": [] if full_details else ["id", "name", "production_id", "state", "duration"],
            "order": "id asc",
        },
    )

    if full_details:
        return records

    result: list[dict[str, Any]] = []
    for rec in records:
        production_raw = rec.get("production_id")
        result.append(
            {
                "id": rec["id"],
                "name": rec.get("name", ""),
                "production_id": production_raw[0] if isinstance(production_raw, list) and production_raw else None,
                "state": rec.get("state"),
                "duration": rec.get("duration"),
            }
        )
    return result


@app.get(
    "/api/v1/orders/operations",
    dependencies=[Depends(verify_api_token)],
    summary="Get operations for production orders",
    description=(
        "Two modes: "
        "1) without op_id returns all operations for order_ids; "
        "2) with op_id returns matching operation across provided order_ids."
    ),
    responses={
        200: {"description": "Operations returned successfully."},
        401: {"description": "Invalid API token."},
        404: {"description": "Operation with provided op_id not found."},
        503: {"description": "Odoo service is unavailable."},
    },
)
def get_operation_details(
    order_ids: list[int] = Query(
        ...,
        description="Required list of Production Order IDs (e.g. ?order_ids=10&order_ids=11).",
    ),
    op_id: int | None = Query(
        default=None,
        description="Optional Work Order ID. If omitted, returns all operations for provided orders.",
    ),
) -> dict[str, Any] | list[dict[str, Any]]:
    if op_id is None:
        return _odoo_safe_execute(
            "mrp.workorder",
            "search_read",
            [[("production_id", "in", order_ids)]],
            {"order": "id asc"},
        )

    records = _odoo_safe_execute("mrp.workorder", "read", [[op_id]], {})
    if not records:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Operation with id '{op_id}' not found.",
        )
    base_operation = records[0]

    operation_name = base_operation.get("name")
    if not operation_name:
        return []

    return _odoo_safe_execute(
        "mrp.workorder",
        "search_read",
        [[("name", "=", operation_name), ("production_id", "in", order_ids)]],
        {"order": "id asc"},
    )


@app.get(
    "/api/v1/departments",
    response_model=list[DepartmentResponse],
    dependencies=[Depends(verify_api_token)],
    summary="Get departments used in operation directory",
    description="Returns unique departments referenced by lavasta.operation.directory.",
)
def get_departments() -> list[DepartmentResponse]:
    directory_records = _odoo_safe_execute(
        "lavasta.operation.directory",
        "search_read",
        [[]],
        {"fields": ["department_id"]},
    )
    department_ids = sorted(
        {
            rec["department_id"][0]
            for rec in directory_records
            if isinstance(rec.get("department_id"), list) and rec["department_id"]
        }
    )
    if not department_ids:
        return []

    departments = _odoo_safe_execute(
        "hr.department",
        "search_read",
        [[("id", "in", department_ids)]],
        {"fields": ["id", "name"], "order": "name asc"},
    )
    return [DepartmentResponse(id=rec["id"], name=rec.get("name", "")) for rec in departments]


@app.post(
    "/api/v1/orders/operations",
    response_model=CreateWorkOrderResponse,
    dependencies=[Depends(verify_api_token)],
    summary="Add operation to production order",
    description="Creates a new mrp.workorder linked to a production order.",
)
def create_order_operation(payload: CreateWorkOrderRequest) -> CreateWorkOrderResponse:
    values: dict[str, Any] = {
        "production_id": payload.production_id,
        "name": payload.name,
        "workcenter_id": payload.workcenter_id,
    }
    if payload.duration_expected is not None:
        values["duration_expected"] = payload.duration_expected

    created_id = _odoo_safe_execute("mrp.workorder", "create", [values])
    return CreateWorkOrderResponse(id=int(created_id))


@app.delete(
    "/api/v1/orders/operations/{workorder_id}",
    dependencies=[Depends(verify_api_token)],
    summary="Delete operation from production order",
    description="Deletes mrp.workorder by ID within the specified production order. Operations in progress or done cannot be deleted.",
)
def delete_order_operation(
    workorder_id: int,
    production_id: int = Query(..., gt=0, description="Production Order ID"),
) -> dict[str, Any]:
    records = _odoo_safe_execute(
        "mrp.workorder",
        "search_read",
        [[("id", "=", workorder_id), ("production_id", "=", production_id)]],
        {"fields": ["id", "state", "production_id"], "limit": 1},
    )
    if not records:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Work order with id '{workorder_id}' "
                f"for production_id '{production_id}' not found."
            ),
        )

    state = records[0].get("state")
    if state in {"progress", "done"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot delete work order in state '{state}'.",
        )

    _odoo_safe_execute("mrp.workorder", "unlink", [[workorder_id]])
    return {"deleted": True, "id": workorder_id, "production_id": production_id}
