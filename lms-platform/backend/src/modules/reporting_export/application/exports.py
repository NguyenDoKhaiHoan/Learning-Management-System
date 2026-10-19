"""Queue commands and live scope checks for private export results."""

import json

from fastapi import HTTPException

from src.modules.reporting_export.application.reports import CourseReports


def public_job(row):
    return {
        key: (
            str(row[key])
            if row[key] is not None and key in {"id", "requested_by", "course_id"}
            else row[key]
        )
        for key in (
            "id",
            "requested_by",
            "course_id",
            "kind",
            "status",
            "row_count",
            "error_code",
            "created_at",
            "completed_at",
            "trace_id",
            "attempt_count",
            "available_at",
        )
    }


class Exports(CourseReports):
    async def scope_for_export(self, kind, course_id):
        # Queue requests and workers use requester -> course -> job lock order.
        user = await self.repo.fetch_one(
            "SELECT status,deleted_at FROM users WHERE id=:id FOR UPDATE", {"id": int(self.user.id)}
        )
        if not user or user["status"] != "ACTIVE" or user["deleted_at"] is not None:
            raise HTTPException(403)
        if kind == "OVERVIEW":
            if "ADMIN" not in self.user.roles:
                raise HTTPException(403)
        else:
            await self.scope(course_id)

    async def create(self, body):
        await self.scope_for_export(body.kind, body.course_id)
        filters = body.filters.model_dump(exclude_none=True)
        params = {"actor": int(self.user.id), "request": str(body.request_id)}
        existing = await self.repo.fetch_one(
            "SELECT * FROM export_jobs WHERE requested_by=:actor AND request_id=:request "
            "FOR UPDATE",
            params,
        )
        if existing:
            if (
                existing["kind"] != body.kind
                or existing["course_id"] != body.course_id
                or json.loads(existing["filters"]) != filters
            ):
                raise HTTPException(409, "Export request identifier reused")
            await self.connection.commit()
            return public_job(existing)
        pending = await self.repo.fetch_one(
            "SELECT COUNT(*) total FROM export_jobs WHERE requested_by=:actor "
            "AND status='PENDING' FOR UPDATE",
            params,
        )
        if pending["total"] >= 3:
            raise HTTPException(409, "Wait for pending exports")
        id = await self.repo.insert(
            """INSERT INTO export_jobs(requested_by,request_id,kind,course_id,filters,trace_id)
            VALUES (:actor,:request,:kind,:course,:filters,:trace)""",
            params
            | {
                "kind": body.kind,
                "course": body.course_id,
                "filters": json.dumps(filters),
                "trace": self.trace_id,
            },
        )
        await self.audit(
            "export.request",
            "export_job",
            id,
            details={
                "kind": body.kind,
                "course_id": str(body.course_id) if body.course_id else None,
                "filters": filters,
            },
        )
        row = await self.repo.fetch_one("SELECT * FROM export_jobs WHERE id=:id", {"id": id})
        await self.connection.commit()
        return public_job(row)

    async def job(self, id):
        row = await self.repo.fetch_one(
            "SELECT * FROM export_jobs WHERE id=:id AND requested_by=:actor",
            {"id": id, "actor": int(self.user.id)},
        )
        if not row:
            raise HTTPException(404)
        await self.scope_for_export(row["kind"], row["course_id"])
        return await self.repo.fetch_one(
            "SELECT * FROM export_jobs WHERE id=:id FOR UPDATE", {"id": id}
        )
