import logging
import threading
import time
from datetime import datetime, timezone

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

from .config import Config
from .data_store import (
    get_registries,
    store_massive_scan_run,
    get_massive_scan_run_history,
)
from .massive_scan import run_massive_scan
from .notifications import send_massive_scan_recap

logger = logging.getLogger(__name__)

_last_run_date = None
_started = False
_status = {
    "running": False,
    "threadActive": False,
    "jobRunning": False,
    "lastRunAt": None,
    "lastRunDate": None,
    "lastRunSummary": None,
    "previousRunSummary": None,
    "lastNotifications": None,
    "lastError": None,
}


def _parse_time_hhmm(value):
    try:
        hour, minute = value.split(":", 1)
        return int(hour), int(minute)
    except Exception:
        return 2, 0


def _resolve_scheduler_timezone():
    # Always use local timezone
    local_tz = datetime.now().astimezone().tzinfo
    return local_tz, "local"


def _resolve_target_registries():
    raw = (Config.MASSIVE_SCAN_REGISTRIES or "all").strip()
    available = [
        r.get("name") for r in get_registries() if isinstance(r, dict) and r.get("name")
    ]
    if raw.lower() == "all":
        return available

    wanted = [x.strip() for x in raw.split(",") if x.strip()]
    return [name for name in wanted if name in available]


def _build_scan_options():
    return {
        "repoPattern": Config.MASSIVE_SCAN_REPO_PATTERN,
        "mode": Config.MASSIVE_SCAN_MODE,
        "ageValue": Config.MASSIVE_SCAN_AGE_VALUE,
        "ageUnit": Config.MASSIVE_SCAN_AGE_UNIT,
        "includeAllTags": Config.MASSIVE_SCAN_INCLUDE_ALL_TAGS,
        "dryRun": Config.MASSIVE_SCAN_DRY_RUN,
    }


def _get_cron_schedule():
    """Return a croniter iterator. If no cron expression is configured,
    fall back to a default daily schedule at 02:00 local time.
    """
    raw = Config.MASSIVE_SCAN_CRON_EXPRESSION
    tzinfo, _ = _resolve_scheduler_timezone()
    base = datetime.now(tz=tzinfo)
    if raw:
        expr = raw
    else:
        # Default to 02:00 daily
        expr = "0 2 * * *"
    try:
        from croniter import croniter
        return croniter(expr, base)
    except Exception as e:
        logger.warning(f"Failed to parse cron expression '{expr}': {e}")
        return None



def _run_scheduled_job(run_at_iso, timezone_label):
    global _status

    registries = get_registries()
    by_name = {
        r.get("name"): r for r in registries if isinstance(r, dict) and r.get("name")
    }
    target_names = _resolve_target_registries()
    if not target_names:
        logger.warning("Scheduled massive scan skipped: no target registries found")
        _status["lastError"] = "no target registries found"
        return

    options = _build_scan_options()
    options["source"] = "scheduled"
    options["timezone"] = timezone_label
    logger.info(
        f"Starting scheduled massive scan for registries: {', '.join(target_names)}"
    )

    aggregate = {
        "runAt": run_at_iso,
        "source": "scheduled",
        "timezone": timezone_label,
        "registryCount": 0,
        "totalImages": 0,
        "totalTags": 0,
        "totalScans": 0,
        "scanned": 0,
        "skipped": 0,
        "errors": 0,
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
        "dryRun": Config.MASSIVE_SCAN_DRY_RUN,
    }
    skipped_due_to_lock = 0

    for name in target_names:
        registry = by_name.get(name)
        if not registry:
            continue
        try:
            result = run_massive_scan(name, registry, options)
            if not result.get("success"):
                if result.get("code") == "massive_scan_in_progress":
                    logger.info(
                        f"Scheduled massive scan skipped for {name}: another worker is already running it"
                    )
                    skipped_due_to_lock += 1
                    continue
                logger.error(
                    f"Scheduled massive scan failed for {name}: {result.get('error', 'unknown error')}"
                )
                _status["lastError"] = result.get("error", "unknown error")
                continue
            notify_result = send_massive_scan_recap(name, result)
            summary = result.get("runSummary") or {}
            aggregate["registryCount"] += 1
            aggregate["totalImages"] += int(summary.get("totalImages", 0) or 0)
            aggregate["totalTags"] += int(summary.get("totalTags", 0) or 0)
            aggregate["totalScans"] += int(summary.get("totalScans", 0) or 0)
            aggregate["scanned"] += int(result.get("scanned", 0) or 0)
            aggregate["skipped"] += int(result.get("skipped", 0) or 0)
            aggregate["errors"] += int(result.get("errors", 0) or 0)
            aggregate["critical"] += int(summary.get("critical", 0) or 0)
            aggregate["high"] += int(summary.get("high", 0) or 0)
            aggregate["medium"] += int(summary.get("medium", 0) or 0)
            aggregate["low"] += int(summary.get("low", 0) or 0)
            _status["lastNotifications"] = notify_result
            _status["lastError"] = None
        except Exception as e:
            logger.error(f"Scheduled massive scan crashed for {name}: {e}")
            _status["lastError"] = str(e)

    # Avoid replacing the current run summary with an empty/zero aggregate when
    # this worker only observed lock contention while another worker is executing.
    if aggregate["registryCount"] == 0 and skipped_due_to_lock > 0:
        logger.info(
            "Skipping scheduler summary update: execution already in progress on another worker"
        )
        return

    prev_summary = _status.get("lastRunSummary")
    if prev_summary:
        _status["previousRunSummary"] = prev_summary
    _status["lastRunSummary"] = aggregate
    store_massive_scan_run("__scheduler__", aggregate)


def _scheduler_loop():
    global _last_run_date, _status

    cron_schedule = _get_cron_schedule()
    if cron_schedule is not None:
        tzinfo, tz_label = _resolve_scheduler_timezone()
        expr = Config.MASSIVE_SCAN_CRON_EXPRESSION or "0 2 * * *"
        logger.info(
            f"Massive scan scheduler active: cron expression '{expr}' ({tz_label})"
        )
        while True:
            try:
                now = datetime.now(tz=tzinfo)
                next_run = cron_schedule.get_next(datetime)
                sleep_seconds = (next_run - now).total_seconds()
                if sleep_seconds > 0:
                    time.sleep(sleep_seconds)
                _status["lastRunAt"] = next_run.isoformat()
                _status["jobRunning"] = True
                try:
                    _run_scheduled_job(_status["lastRunAt"], tz_label)
                finally:
                    _status["jobRunning"] = False
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")
                _status["lastError"] = str(e)
                _status["jobRunning"] = False
    else:
        # This should never happen with the new cron-based scheduler
        logger.error("No cron schedule available, scheduler disabled")
        _status["running"] = False
        _status["threadActive"] = False
        _status["jobRunning"] = False


def start_scheduler_if_enabled():
    global _started, _status
    if _started:
        return
    if not Config.MASSIVE_SCAN_SCHEDULE_ENABLED:
        logger.info("Massive scan scheduler is disabled")
        _status["running"] = False
        _status["threadActive"] = False
        _status["jobRunning"] = False
        return

    thread = threading.Thread(
        target=_scheduler_loop, daemon=True, name="massive-scan-scheduler"
    )
    thread.start()
    _started = True
    _status["threadActive"] = True
    _status["running"] = False


def get_scheduler_status():
    """Return runtime scheduler status for API/UI."""
    last_summary = _status.get("lastRunSummary")
    prev_summary = _status.get("previousRunSummary")
    if not last_summary:
        history = get_massive_scan_run_history("__scheduler__", limit=2)
        if history:
            last_summary = history[0]
        if len(history) > 1:
            prev_summary = history[1]

    # Determine schedule info
    cron_expr = Config.MASSIVE_SCAN_CRON_EXPRESSION
    if cron_expr:
        schedule_info = {"cronExpression": cron_expr.strip()}
        schedule_time = cron_expr.strip()
    else:
        # Default to daily at 02:00 local
        schedule_info = {"defaultTime": "02:00"}
        schedule_time = "02:00 (daily)"

    return {
        "enabled": Config.MASSIVE_SCAN_SCHEDULE_ENABLED,
        "running": _status.get("jobRunning", False),
        "threadActive": _status.get("threadActive", False),
        "jobRunning": _status.get("jobRunning", False),
        "scheduleInfo": schedule_info,
        "scheduleTime": schedule_time,
        "timezone": "local",
        "targetRegistries": Config.MASSIVE_SCAN_REGISTRIES,
        "mode": Config.MASSIVE_SCAN_MODE,
        "repoPattern": Config.MASSIVE_SCAN_REPO_PATTERN,
        "includeAllTags": Config.MASSIVE_SCAN_INCLUDE_ALL_TAGS,
        "dryRun": Config.MASSIVE_SCAN_DRY_RUN,
        "lastRunAt": _status.get("lastRunAt"),
        "lastRunDate": _status.get("lastRunDate"),
        "lastRunSummary": last_summary,
        "previousRunSummary": prev_summary,
        "lastNotifications": _status.get("lastNotifications"),
        "lastError": _status.get("lastError"),
    }
