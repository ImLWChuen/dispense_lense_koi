import logging
import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin
from app.core import security
from app.db.session import get_db
from app.models.case import (
    CaseCauseConfirmationModel,
    CaseCheckResultModel,
    CaseLifecycleEventModel,
    CaseModel,
)
from app.models.user import UserModel
from app.schemas.user import (
    AdminOverviewStats,
    AdminResetPassword,
    AdminUserCreate,
    AdminUserUpdate,
    EmployeeSummary,
    UserRead,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/overview", response_model=AdminOverviewStats)
def get_admin_overview(
    db: Session = Depends(get_db),
    admin_user: UserModel = Depends(require_admin),
) -> AdminOverviewStats:
    """Retrieve executive oversight metrics across all employees and diagnostic operations."""
    users = db.query(UserModel).all()
    total_employees = len(users)
    active_employees = sum(1 for u in users if u.is_active)
    inactive_employees = total_employees - active_employees

    role_breakdown: dict[str, int] = {}
    department_breakdown: dict[str, int] = {}

    for u in users:
        role = u.role or "unassigned"
        role_breakdown[role] = role_breakdown.get(role, 0) + 1

        dept = u.department or "General Operations"
        department_breakdown[dept] = department_breakdown.get(dept, 0) + 1

    # Case metrics
    total_cases = db.query(CaseModel).count()
    resolved_cases = db.query(CaseModel).filter(CaseModel.issue_condition == "RESOLVED").count()
    unresolved_cases = total_cases - resolved_cases

    # Recent employee / system activities
    recent_activities: list[dict[str, Any]] = []

    # 1. Lifecycle events
    events = (
        db.query(CaseLifecycleEventModel)
        .order_by(CaseLifecycleEventModel.created_at.desc())
        .limit(10)
        .all()
    )
    for ev in events:
        recent_activities.append(
            {
                "id": f"lifecycle_{ev.id}",
                "type": "LIFECYCLE",
                "title": f"Lifecycle: {ev.resulting_issue_condition}",
                "description": ev.details or f"Transitioned from {ev.prior_issue_condition}",
                "actor": ev.actor or "Technician",
                "timestamp": ev.created_at.isoformat() if ev.created_at else None,
            }
        )

    # 2. Confirmations
    confirmations = (
        db.query(CaseCauseConfirmationModel)
        .order_by(CaseCauseConfirmationModel.confirmed_at.desc())
        .limit(8)
        .all()
    )
    for conf in confirmations:
        recent_activities.append(
            {
                "id": f"cause_{conf.id}",
                "type": "CAUSE_CONFIRMATION",
                "title": f"Confirmed Root Cause: {conf.cause_id}",
                "description": conf.notes or "Technician root cause confirmation verified.",
                "actor": conf.confirmed_by or "Technician",
                "timestamp": conf.confirmed_at.isoformat() if conf.confirmed_at else None,
            }
        )

    # Sort activities by timestamp descending
    recent_activities.sort(key=lambda x: x.get("timestamp") or "", reverse=True)
    recent_activities = recent_activities[:15]

    return AdminOverviewStats(
        total_employees=total_employees,
        active_employees=active_employees,
        inactive_employees=inactive_employees,
        role_breakdown=role_breakdown,
        department_breakdown=department_breakdown,
        total_cases_monitored=total_cases,
        resolved_cases_count=resolved_cases,
        unresolved_cases_count=unresolved_cases,
        recent_activities=recent_activities,
    )


@router.get("/users", response_model=list[EmployeeSummary])
def list_employees(
    search: Optional[str] = Query(None, description="Search by name, email, or department"),
    role: Optional[str] = Query(None, description="Filter by employee role"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: Session = Depends(get_db),
    admin_user: UserModel = Depends(require_admin),
) -> list[EmployeeSummary]:
    """Retrieve all employees with workload metrics, filtering, and status."""
    query = db.query(UserModel)

    if isinstance(search, str) and search.strip():
        term = f"%{search.strip().lower()}%"
        query = query.filter(
            func.lower(UserModel.email).like(term)
            | func.lower(UserModel.first_name).like(term)
            | func.lower(UserModel.last_name).like(term)
            | func.lower(UserModel.department).like(term)
        )

    if isinstance(role, str) and role.strip() and role.lower() != "all":
        query = query.filter(UserModel.role == role.strip().lower())

    if isinstance(is_active, bool):
        query = query.filter(UserModel.is_active == is_active)

    users = query.order_by(UserModel.created_at.asc()).all()

    # Calculate activity metrics
    results: list[EmployeeSummary] = []
    for u in users:
        # Check confirmations or actions performed by user
        # Note: in this domain, technician actions may record confirmed_by or performed_by matching email or name or role
        # Count confirmations and lifecycle actions by user
        user_identifier = u.email
        first_name = u.first_name or ""

        cases_handled = (
            db.query(CaseCauseConfirmationModel)
            .filter(
                (CaseCauseConfirmationModel.confirmed_by == user_identifier)
                | (CaseCauseConfirmationModel.confirmed_by == first_name)
                | (CaseCauseConfirmationModel.confirmed_by.ilike(f"%{u.role}%"))
            )
            .count()
        )

        actions_performed = (
            db.query(CaseLifecycleEventModel)
            .filter(
                (CaseLifecycleEventModel.actor == user_identifier)
                | (CaseLifecycleEventModel.actor == first_name)
                | (CaseLifecycleEventModel.actor.ilike(f"%{u.role}%"))
            )
            .count()
        )

        results.append(
            EmployeeSummary(
                id=u.id,
                email=u.email,
                first_name=u.first_name,
                last_name=u.last_name,
                role=u.role,
                department=u.department,
                is_active=u.is_active,
                created_at=u.created_at,
                last_login=u.last_login,
                cases_handled=cases_handled,
                actions_performed=actions_performed,
            )
        )

    return results


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_employee(
    payload: AdminUserCreate,
    db: Session = Depends(get_db),
    admin_user: UserModel = Depends(require_admin),
) -> UserRead:
    """Create a new employee account with specified role and department."""
    existing = db.query(UserModel).filter(UserModel.email == payload.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User with email '{payload.email}' already exists.",
        )

    new_user = UserModel(
        id=str(uuid.uuid4()),
        email=payload.email,
        hashed_password=security.get_password_hash(payload.password),
        first_name=payload.first_name,
        last_name=payload.last_name,
        role=payload.role.lower(),
        department=payload.department,
        is_active=payload.is_active,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    logger.info("Admin %s created new employee %s (%s)", admin_user.email, new_user.email, new_user.role)
    return new_user


@router.put("/users/{user_id}", response_model=UserRead)
def update_employee(
    user_id: str,
    payload: AdminUserUpdate,
    db: Session = Depends(get_db),
    admin_user: UserModel = Depends(require_admin),
) -> UserRead:
    """Update employee details, role, department, or active status."""
    target_user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found.")

    # Guardrails: prevent an admin from deactivating or demoting their own active account
    if target_user.id == admin_user.id:
        if payload.is_active is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot deactivate your own administrator account.",
            )
        if payload.role and payload.role.lower() != "admin":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot demote your own administrator account.",
            )

    if payload.email is not None and payload.email != target_user.email:
        existing_email = db.query(UserModel).filter(UserModel.email == payload.email).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Email '{payload.email}' is already in use by another user.",
            )
        target_user.email = payload.email

    if payload.first_name is not None:
        target_user.first_name = payload.first_name
    if payload.last_name is not None:
        target_user.last_name = payload.last_name
    if payload.role is not None:
        target_user.role = payload.role.lower()
    if payload.department is not None:
        target_user.department = payload.department
    if payload.is_active is not None:
        target_user.is_active = payload.is_active

    db.add(target_user)
    db.commit()
    db.refresh(target_user)
    logger.info("Admin %s updated employee %s", admin_user.email, target_user.email)
    return target_user


@router.post("/users/{user_id}/reset-password")
def reset_employee_password(
    user_id: str,
    payload: AdminResetPassword,
    db: Session = Depends(get_db),
    admin_user: UserModel = Depends(require_admin),
) -> dict[str, str]:
    """Administratively reset an employee's password."""
    target_user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found.")

    if len(payload.new_password.strip()) < 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 4 characters long.",
        )

    target_user.hashed_password = security.get_password_hash(payload.new_password)
    db.add(target_user)
    db.commit()
    logger.info("Admin %s reset password for employee %s", admin_user.email, target_user.email)
    return {"message": f"Password for {target_user.email} was successfully reset."}


@router.delete("/users/{user_id}")
def delete_or_deactivate_employee(
    user_id: str,
    hard_delete: bool = Query(False, description="Set True to permanently purge user record"),
    db: Session = Depends(get_db),
    admin_user: UserModel = Depends(require_admin),
) -> dict[str, str]:
    """Deactivate or remove an employee account."""
    target_user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found.")

    if target_user.id == admin_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete or deactivate your own administrator account.",
        )

    if hard_delete:
        db.delete(target_user)
        db.commit()
        return {"message": f"Employee {target_user.email} permanently removed."}
    else:
        target_user.is_active = False
        db.add(target_user)
        db.commit()
        return {"message": f"Employee {target_user.email} deactivated."}
