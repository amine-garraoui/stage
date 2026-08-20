"""RBAC permission definitions."""

from __future__ import annotations

PERMISSIONS: dict[str, frozenset[str]] = {
    "ADMIN": frozenset({
        "login", "import_files", "generate_kpis", "recalculate_indicators",
        "manage_users", "view_dashboards", "view_reports", "export_pdf",
        "export_excel", "view_audit_logs", "view_anomaly_reports",
        "manage_settings", "delete_data", "view_kpis", "view_trends", "view_forecasts",
    }),
    "USER": frozenset({
        "login", "view_dashboards", "view_kpis",
        "view_reports", "view_trends", "view_forecasts",
    }),
}


def has_permission(role: str, permission: str) -> bool:
    return permission in PERMISSIONS.get(role, frozenset())


def check_permission(role: str, permission: str) -> None:
    if not has_permission(role, permission):
        raise PermissionError(f"Rôle '{role}' n'a pas la permission '{permission}'.")
