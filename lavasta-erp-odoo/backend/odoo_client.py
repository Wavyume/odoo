import os
import socket
import xmlrpc.client
from datetime import datetime, timedelta, timezone
from typing import Any


class OdooConnectionError(Exception):
    """Raised when Odoo is unavailable or authentication fails."""


class OdooClient:
    def __init__(self) -> None:
        self.url = os.getenv("ODOO_URL", "http://odoo:8069")
        self.db = os.getenv("ODOO_DB", "")
        self.username = os.getenv("ODOO_USER", "")
        self.password = os.getenv("ODOO_PASSWORD", "")

        self.uid: int | None = None
        self._common: xmlrpc.client.ServerProxy | None = None
        self._models: xmlrpc.client.ServerProxy | None = None

    def connect(self) -> None:
        """Initialize XML-RPC proxies and authenticate user."""
        try:
            self._common = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common")
            self._models = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object")
            uid = self._common.authenticate(self.db, self.username, self.password, {})
        except (OSError, socket.error, xmlrpc.client.Error) as exc:
            raise OdooConnectionError(f"Failed to connect to Odoo: {exc}") from exc

        if not uid:
            raise OdooConnectionError("Odoo authentication failed. Check DB/user/password.")

        self.uid = uid

    def _ensure_connected(self) -> None:
        if self.uid is None or self._models is None or self._common is None:
            self.connect()

    def execute_kw(
        self,
        model: str,
        method: str,
        args: list[Any] | None = None,
        kwargs: dict[str, Any] | None = None,
    ) -> Any:
        """Execute an Odoo model method with reconnect on first failure."""
        args = args or []
        kwargs = kwargs or {}

        self._ensure_connected()

        try:
            return self._models.execute_kw(  # type: ignore[union-attr]
                self.db,
                self.uid,
                self.password,
                model,
                method,
                args,
                kwargs,
            )
        except (OSError, socket.error, xmlrpc.client.Error) as exc:
            # Odoo can be booting/restarting; clear session and try once again.
            self.uid = None
            self._common = None
            self._models = None
            try:
                self._ensure_connected()
                return self._models.execute_kw(  # type: ignore[union-attr]
                    self.db,
                    self.uid,
                    self.password,
                    model,
                    method,
                    args,
                    kwargs,
                )
            except (OSError, socket.error, xmlrpc.client.Error) as second_exc:
                raise OdooConnectionError(
                    f"Odoo RPC call failed ({model}.{method}): {second_exc}"
                ) from exc

    @staticmethod
    def _utc_now_odoo() -> str:
        """Return current UTC datetime in Odoo-compatible string format."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _utc_today_bounds() -> tuple[str, str]:
        """Return UTC day start/end bounds for robust 'today' filtering."""
        now_utc = datetime.now(timezone.utc)
        day_start = datetime(
            now_utc.year,
            now_utc.month,
            now_utc.day,
            0,
            0,
            0,
            tzinfo=timezone.utc,
        )
        day_end = day_start + timedelta(days=1)
        return (
            day_start.strftime("%Y-%m-%d %H:%M:%S"),
            day_end.strftime("%Y-%m-%d %H:%M:%S"),
        )

    def get_today_attendance(self, employee_id: int) -> list[dict[str, Any]]:
        """Get attendance entries for an employee for current UTC day."""
        start_utc, end_utc = self._utc_today_bounds()
        domain = [
            ("employee_id", "=", employee_id),
            ("check_in", ">=", start_utc),
            ("check_in", "<", end_utc),
        ]
        return self.execute_kw(
            "hr.attendance",
            "search_read",
            [domain],
            {
                "fields": ["id", "check_in", "check_out", "lavasta_attendance_status"],
                "order": "check_in desc",
            },
        )

    def attendance_action(
        self,
        employee_id: int,
        action: str,
        status: str | None = None,
        manual_time: str | None = None,
    ) -> int:
        """
        Start or end employee attendance.
        - start: create open attendance with manual_time or current UTC check_in
        - end: close latest open attendance (check_out is false) with manual_time or now
        """
        effective_time = manual_time or self._utc_now_odoo()

        if action == "start":
            values: dict[str, Any] = {
                "employee_id": employee_id,
                "check_in": effective_time,
            }
            values["lavasta_attendance_status"] = status
            return int(self.execute_kw("hr.attendance", "create", [values]))

        if action == "end":
            open_records = self.execute_kw(
                "hr.attendance",
                "search_read",
                [[("employee_id", "=", employee_id), ("check_out", "=", False)]],
                {"fields": ["id"], "limit": 1, "order": "check_in desc"},
            )
            if not open_records:
                raise ValueError("No open attendance found to close.")

            attendance_id = int(open_records[0]["id"])
            values = {
                "check_out": effective_time,
                "lavasta_attendance_status": status,
            }

            self.execute_kw("hr.attendance", "write", [[attendance_id], values])
            return attendance_id

        raise ValueError("Unsupported action. Use 'start' or 'end'.")
