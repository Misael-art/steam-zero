// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 SteamZero contributors
.pragma library

function componentJobOutcome(job) {
    if (!job || job.type !== "component.apply")
        return "not-component"

    const rawState = String(job.rawState || "")
    if (["created", "queued", "blocked", "paused"].indexOf(rawState) >= 0)
        return "pending"
    if (["running", "cancelling", "interrupted", "rolling-back"].indexOf(rawState) >= 0)
        return "running"
    if (rawState === "completed")
        return "succeeded"
    if (rawState === "cancelled")
        return "cancelled"
    if (rawState === "rollback-failed")
        return "rollback-failed"
    if (rawState === "rolled-back")
        return job.operationId ? "rollback-complete" : "failure-unlinked"
    if (rawState === "failed")
        return "failed"
    return "unknown"
}

function componentJobTrace(job) {
    if (!job || job.type !== "component.apply")
        return {}
    const identity = [job.adapterId, job.action, job.executor]
        .filter(function(value) { return typeof value === "string" && value.length > 0 })
        .join(" · ")
    return {
        "identity": identity,
        "artifact": String(job.artifact || ""),
        "targetVersion": String(job.targetVersion || ""),
        "sourceRevision": String(job.sourceRevision || ""),
        "artifactDigest": String(job.artifactDigest || ""),
        "correlationId": String(job.correlationId || ""),
        "jobId": String(job.jobId || ""),
        "planId": String(job.planId || ""),
        "operationId": String(job.operationId || "")
    }
}
