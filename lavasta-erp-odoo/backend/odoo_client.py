import os
import socket
import xmlrpc.client
from typing import Any


class OdooConnectionError(Exception):
    """Raised when Odoo is unavailable or authentication fails."""


class OdooClient:
    def __init__(self) -> None:
        self.url = os.getenv("ODOO_URL", "http://localhost:8069")
        self.db = os.getenv("ODOO_DB", "testovaya")
        self.username = os.getenv("ODOO_USER", "admin")
        self.password = os.getenv("ODOO_PASSWORD", "}[Ub0({c1|3X8a3m6z?£EKd")

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
