"""
OmniTrade Pro — Enterprise Token Bucket Rate Limiter, IP Throttler & DoS Defense Engine
==========================================================================================
Provides institutional-grade rate limiting, per-IP sliding burst throttling, and active DoS
mitigation for SaaS APIs, Webhooks, and Multi-Tenant Endpoints.

Components:
- TokenBucket: High-precision token bucket rate limiter with monotonic fractional refill.
- IPThrottler: Per-IP dynamic token bucket manager with whitelist and auto-cleanup.
- DoSDefenseGuard: Volumetric burst detection, automated IP blacklisting/banning, and telemetry.
- TenantRateLimiter: Subscription-tier aware API key rate enforcement.
- RateLimitAndDoSMiddleware: ASGI middleware for FastAPI / Starlette integration.
"""

import time
import threading
import logging
from typing import Dict, Any, Tuple, Optional, Set, List
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger("OmniTrade.RateLimiter")


class TokenBucket:
    """
    High-precision Token Bucket Algorithm with continuous fractional refill.
    Thread-safe implementation using monotonic clock for leap-second and clock-drift resilience.
    """

    def __init__(self, capacity: float, refill_rate: float, initial_tokens: Optional[float] = None):
        """
        :param capacity: Maximum number of tokens the bucket can hold (burst limit).
        :param refill_rate: Number of tokens added to the bucket per second.
        :param initial_tokens: Initial tokens in bucket (defaults to capacity).
        """
        if capacity <= 0:
            raise ValueError("Capacity must be positive.")
        if refill_rate <= 0:
            raise ValueError("Refill rate must be positive.")

        self.capacity = float(capacity)
        self.refill_rate = float(refill_rate)
        self.tokens = float(capacity if initial_tokens is None else min(initial_tokens, capacity))
        self.last_refill = time.monotonic()
        self.lock = threading.Lock()

    def _refill(self, now: float) -> None:
        elapsed = now - self.last_refill
        if elapsed > 0:
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
            self.last_refill = now

    def consume(self, cost: float = 1.0) -> Tuple[bool, Dict[str, Any]]:
        """
        Attempts to consume `cost` tokens from the bucket.
        :return: (allowed: bool, details: dict)
        """
        with self.lock:
            now = time.monotonic()
            self._refill(now)

            if self.tokens >= cost:
                self.tokens -= cost
                return True, {
                    "allowed": True,
                    "remaining": int(self.tokens),
                    "capacity": int(self.capacity),
                    "retry_after": 0.0,
                    "refill_rate": self.refill_rate,
                }
            else:
                deficit = cost - self.tokens
                retry_after = round(deficit / self.refill_rate, 3)
                return False, {
                    "allowed": False,
                    "remaining": int(self.tokens),
                    "capacity": int(self.capacity),
                    "retry_after": max(0.001, retry_after),
                    "refill_rate": self.refill_rate,
                }

    def get_state(self) -> Dict[str, Any]:
        with self.lock:
            now = time.monotonic()
            self._refill(now)
            return {
                "capacity": self.capacity,
                "current_tokens": round(self.tokens, 2),
                "refill_rate": self.refill_rate,
            }

    def reset(self) -> None:
        with self.lock:
            self.tokens = self.capacity
            self.last_refill = time.monotonic()


class IPThrottler:
    """
    Manages per-IP token buckets with dynamic creation and periodic cleanup.
    """

    def __init__(self, default_capacity: float = 30.0, default_refill_rate: float = 5.0):
        self.default_capacity = default_capacity
        self.default_refill_rate = default_refill_rate
        self.buckets: Dict[str, TokenBucket] = {}
        self.last_active: Dict[str, float] = {}
        self.whitelist: Set[str] = set()
        self.lock = threading.Lock()

    def add_whitelist(self, ip: str) -> None:
        with self.lock:
            self.whitelist.add(ip)

    def remove_whitelist(self, ip: str) -> None:
        with self.lock:
            self.whitelist.discard(ip)

    def is_whitelisted(self, ip: str) -> bool:
        with self.lock:
            return ip in self.whitelist

    def check_ip(self, ip: str, cost: float = 1.0) -> Tuple[bool, Dict[str, Any]]:
        if self.is_whitelisted(ip):
            return True, {
                "allowed": True,
                "whitelisted": True,
                "remaining": int(self.default_capacity),
                "capacity": int(self.default_capacity),
                "retry_after": 0.0,
            }

        with self.lock:
            now = time.monotonic()
            self.last_active[ip] = now
            if ip not in self.buckets:
                self.buckets[ip] = TokenBucket(
                    capacity=self.default_capacity,
                    refill_rate=self.default_refill_rate
                )
            bucket = self.buckets[ip]

        allowed, info = bucket.consume(cost)
        info["whitelisted"] = False
        return allowed, info

    def cleanup_idle(self, max_idle_seconds: float = 300.0) -> int:
        """Removes IP buckets inactive for longer than max_idle_seconds."""
        with self.lock:
            now = time.monotonic()
            stale_ips = [
                ip for ip, last in self.last_active.items()
                if (now - last) > max_idle_seconds
            ]
            for ip in stale_ips:
                self.buckets.pop(ip, None)
                self.last_active.pop(ip, None)
            return len(stale_ips)

    def reset(self) -> None:
        with self.lock:
            self.buckets.clear()
            self.last_active.clear()


class DoSDefenseGuard:
    """
    Active DoS Defense & IP Ban Engine.
    Detects volumetric traffic bursts and repeated rate-limit violations,
    automatically banning offending IPs and maintaining real-time mitigation telemetry.
    """

    def __init__(
        self,
        burst_window_seconds: float = 2.0,
        burst_threshold: int = 35,
        violation_threshold: int = 5,
        ban_duration_seconds: float = 60.0,
        capacity_per_ip: float = 30.0,
        refill_rate_per_ip: float = 5.0,
    ):
        self.burst_window_seconds = burst_window_seconds
        self.burst_threshold = burst_threshold
        self.violation_threshold = violation_threshold
        self.ban_duration_seconds = ban_duration_seconds

        self.throttler = IPThrottler(
            default_capacity=capacity_per_ip,
            default_refill_rate=refill_rate_per_ip
        )
        self.banned_ips: Dict[str, Dict[str, Any]] = {}
        self.burst_history: Dict[str, List[float]] = {}
        self.violation_counts: Dict[str, int] = {}
        self.lock = threading.Lock()

        # Telemetry metrics
        self.telemetry = {
            "total_requests": 0,
            "allowed_requests": 0,
            "throttled_requests": 0,
            "blocked_banned_requests": 0,
            "dos_mitigations_triggered": 0,
            "active_bans_count": 0,
            "recent_violations": []
        }

    def add_whitelist(self, ip: str) -> None:
        self.throttler.add_whitelist(ip)

    def remove_whitelist(self, ip: str) -> None:
        self.throttler.remove_whitelist(ip)

    def is_whitelisted(self, ip: str) -> bool:
        return self.throttler.is_whitelisted(ip)

    def ban_ip(self, ip: str, duration: Optional[float] = None, reason: str = "Volumetric DoS attack detected") -> None:
        duration = duration if duration is not None else self.ban_duration_seconds
        now = time.time()
        with self.lock:
            self.banned_ips[ip] = {
                "ip": ip,
                "banned_at": now,
                "expires_at": now + duration,
                "reason": reason,
                "duration": duration,
            }
            self.telemetry["dos_mitigations_triggered"] += 1
            self.telemetry["active_bans_count"] = len(self.banned_ips)
            self._log_violation(ip, "BAN", reason)
        logger.warning(f"🚨 [DoS Defense] IP {ip} BANNED for {duration}s. Reason: {reason}")

    def unban_ip(self, ip: str) -> bool:
        with self.lock:
            if ip in self.banned_ips:
                del self.banned_ips[ip]
                self.violation_counts.pop(ip, None)
                self.telemetry["active_bans_count"] = len(self.banned_ips)
                logger.info(f"✅ [DoS Defense] IP {ip} unbanned manually.")
                return True
            return False

    def is_banned(self, ip: str) -> Tuple[bool, float, str]:
        """
        Checks if IP is currently banned.
        :return: (is_banned: bool, remaining_seconds: float, reason: str)
        """
        now = time.time()
        with self.lock:
            if ip in self.banned_ips:
                info = self.banned_ips[ip]
                remaining = info["expires_at"] - now
                if remaining > 0:
                    return True, round(remaining, 1), info.get("reason", "Banned")
                else:
                    # Ban expired
                    del self.banned_ips[ip]
                    self.violation_counts.pop(ip, None)
                    self.telemetry["active_bans_count"] = len(self.banned_ips)
            return False, 0.0, ""

    def _log_violation(self, ip: str, action: str, details: str) -> None:
        event = {
            "timestamp": time.time(),
            "ip": ip,
            "action": action,
            "details": details
        }
        recent = self.telemetry["recent_violations"]
        recent.append(event)
        if len(recent) > 100:
            recent.pop(0)

    def evaluate_request(self, ip: str, endpoint: str = "") -> Dict[str, Any]:
        """
        Full evaluation pipeline:
        1. Check IP Ban list.
        2. Check for volumetric sudden burst (DoS).
        3. Consume token bucket.
        4. Track violation counts.
        """
        # Step 0: Whitelist check
        if self.is_whitelisted(ip):
            with self.lock:
                self.telemetry["total_requests"] += 1
                self.telemetry["allowed_requests"] += 1
            return {
                "action": "ALLOW",
                "status_code": 200,
                "reason": "Whitelisted IP",
                "retry_after": 0.0,
                "remaining": 999,
                "headers": {
                    "X-RateLimit-Limit": "unlimited",
                    "X-RateLimit-Remaining": "999",
                    "X-RateLimit-Reset": "0",
                }
            }

        # Step 1: Active Ban Check
        banned, remaining_ban, reason = self.is_banned(ip)
        if banned:
            with self.lock:
                self.telemetry["total_requests"] += 1
                self.telemetry["blocked_banned_requests"] += 1
            return {
                "action": "BLOCK",
                "status_code": 403,
                "reason": f"IP temporarily banned due to DoS defense: {reason}",
                "retry_after": remaining_ban,
                "remaining": 0,
                "headers": {
                    "Retry-After": str(int(remaining_ban)),
                    "X-RateLimit-Limit": "0",
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(remaining_ban)),
                }
            }

        # Step 2: Volumetric Burst Detection
        now_mono = time.monotonic()
        with self.lock:
            self.telemetry["total_requests"] += 1
            if ip not in self.burst_history:
                self.burst_history[ip] = []
            
            # Prune old timestamps outside the window
            cutoff = now_mono - self.burst_window_seconds
            self.burst_history[ip] = [t for t in self.burst_history[ip] if t >= cutoff]
            self.burst_history[ip].append(now_mono)
            burst_count = len(self.burst_history[ip])

        if burst_count > self.burst_threshold:
            # Immediate DoS Auto-Ban
            self.ban_ip(
                ip,
                duration=self.ban_duration_seconds,
                reason=f"Volumetric burst detected: {burst_count} reqs in {self.burst_window_seconds}s (limit {self.burst_threshold})"
            )
            with self.lock:
                self.telemetry["blocked_banned_requests"] += 1
            return {
                "action": "BLOCK",
                "status_code": 403,
                "reason": "DoS mitigation triggered: excessive burst rate",
                "retry_after": self.ban_duration_seconds,
                "remaining": 0,
                "headers": {
                    "Retry-After": str(int(self.ban_duration_seconds)),
                    "X-RateLimit-Limit": "0",
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(self.ban_duration_seconds)),
                }
            }

        # Step 3: Token Bucket Rate Limiting
        allowed, info = self.throttler.check_ip(ip)

        if allowed:
            with self.lock:
                self.telemetry["allowed_requests"] += 1
                # Reset violations upon healthy request
                if ip in self.violation_counts and self.violation_counts[ip] > 0:
                    self.violation_counts[ip] = max(0, self.violation_counts[ip] - 1)

            return {
                "action": "ALLOW",
                "status_code": 200,
                "reason": "Request permitted",
                "retry_after": 0.0,
                "remaining": info["remaining"],
                "headers": {
                    "X-RateLimit-Limit": str(info["capacity"]),
                    "X-RateLimit-Remaining": str(info["remaining"]),
                    "X-RateLimit-Reset": "0",
                }
            }
        else:
            # Rate limit exceeded -> increment violation count
            with self.lock:
                self.telemetry["throttled_requests"] += 1
                violations = self.violation_counts.get(ip, 0) + 1
                self.violation_counts[ip] = violations
                self._log_violation(ip, "THROTTLE", f"Violation count: {violations}/{self.violation_threshold}")

            # Check if repeat violations warrant an auto-ban
            if violations >= self.violation_threshold:
                self.ban_ip(
                    ip,
                    duration=self.ban_duration_seconds,
                    reason=f"Repeated rate limit violations: {violations} consecutive 429s"
                )
                with self.lock:
                    self.telemetry["blocked_banned_requests"] += 1
                return {
                    "action": "BLOCK",
                    "status_code": 403,
                    "reason": "DoS mitigation triggered: sustained rate limit violations",
                    "retry_after": self.ban_duration_seconds,
                    "remaining": 0,
                    "headers": {
                        "Retry-After": str(int(self.ban_duration_seconds)),
                        "X-RateLimit-Limit": "0",
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(int(self.ban_duration_seconds)),
                    }
                }

            retry_after = info["retry_after"]
            return {
                "action": "THROTTLE",
                "status_code": 429,
                "reason": "Client rate limit exceeded (Token bucket depleted)",
                "retry_after": retry_after,
                "remaining": info["remaining"],
                "headers": {
                    "Retry-After": str(max(1, int(retry_after))),
                    "X-RateLimit-Limit": str(info["capacity"]),
                    "X-RateLimit-Remaining": str(info["remaining"]),
                    "X-RateLimit-Reset": str(max(1, int(retry_after))),
                }
            }

    def get_telemetry(self) -> Dict[str, Any]:
        with self.lock:
            active_bans = [
                {
                    "ip": ip,
                    "expires_in_sec": round(max(0, info["expires_at"] - time.time()), 1),
                    "reason": info["reason"]
                }
                for ip, info in self.banned_ips.items()
                if info["expires_at"] > time.time()
            ]
            return {
                "active_bans_count": len(active_bans),
                "active_bans": active_bans,
                "total_requests": self.telemetry["total_requests"],
                "allowed_requests": self.telemetry["allowed_requests"],
                "throttled_requests": self.telemetry["throttled_requests"],
                "blocked_banned_requests": self.telemetry["blocked_banned_requests"],
                "dos_mitigations_triggered": self.telemetry["dos_mitigations_triggered"],
                "recent_violations": list(self.telemetry["recent_violations"][-10:])
            }

    def reset(self) -> None:
        with self.lock:
            self.banned_ips.clear()
            self.burst_history.clear()
            self.violation_counts.clear()
            self.telemetry = {
                "total_requests": 0,
                "allowed_requests": 0,
                "throttled_requests": 0,
                "blocked_banned_requests": 0,
                "dos_mitigations_triggered": 0,
                "active_bans_count": 0,
                "recent_violations": []
            }
        self.throttler.reset()


class TenantRateLimiter:
    """
    Tier-aware API Key Rate Limiter for SaaS Multi-Tenancy.
    Tiers:
    - Starter: 60 RPM (capacity: 15, refill: 1.0 tokens/s)
    - Pro: 300 RPM (capacity: 50, refill: 5.0 tokens/s)
    - Institutional: 600 RPM (capacity: 100, refill: 10.0 tokens/s)
    """

    TIER_DEFAULTS = {
        "tier_starter": {"capacity": 15.0, "refill_rate": 1.0},
        "tier_pro": {"capacity": 50.0, "refill_rate": 5.0},
        "tier_institutional": {"capacity": 100.0, "refill_rate": 10.0},
    }

    def __init__(self):
        self.key_buckets: Dict[str, TokenBucket] = {}
        self.lock = threading.Lock()

    def check_api_key(
        self,
        api_key: str,
        tier: str = "tier_starter",
        custom_rpm: Optional[int] = None,
        cost: float = 1.0
    ) -> Tuple[bool, Dict[str, Any]]:
        with self.lock:
            if api_key not in self.key_buckets:
                if custom_rpm and custom_rpm > 0:
                    refill_rate = max(0.1, custom_rpm / 60.0)
                    capacity = max(10.0, float(min(custom_rpm, 100)))
                else:
                    cfg = self.TIER_DEFAULTS.get(tier, self.TIER_DEFAULTS["tier_starter"])
                    capacity = cfg["capacity"]
                    refill_rate = cfg["refill_rate"]

                self.key_buckets[api_key] = TokenBucket(capacity=capacity, refill_rate=refill_rate)

            bucket = self.key_buckets[api_key]

        return bucket.consume(cost)

    def reset(self) -> None:
        with self.lock:
            self.key_buckets.clear()


class RateLimitAndDoSMiddleware(BaseHTTPMiddleware):
    """
    FastAPI / Starlette ASGI Middleware providing Layer 1 DoS Defense & IP Throttling.
    """

    def __init__(
        self,
        app,
        guard: Optional[DoSDefenseGuard] = None,
        exempt_paths: Optional[Set[str]] = None,
    ):
        super().__init__(app)
        self.guard = guard or DoSDefenseGuard()
        self.exempt_paths = exempt_paths or {"/docs", "/redoc", "/openapi.json"}

    def _extract_client_ip(self, request: Request) -> str:
        # Check X-Forwarded-For header first (first IP in chain)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            ip = forwarded_for.split(",")[0].strip()
            if ip:
                return ip

        # Check X-Real-IP
        real_ip = request.headers.get("x-real-ip")
        if real_ip and real_ip.strip():
            return real_ip.strip()

        # Fallback to direct client host
        if request.client and request.client.host:
            return request.client.host

        return "127.0.0.1"

    async def dispatch(self, request: Request, call_next) -> Response:
        # Exempt static docs or internal health endpoints if requested
        if request.url.path in self.exempt_paths:
            return await call_next(request)

        client_ip = self._extract_client_ip(request)
        eval_result = self.guard.evaluate_request(client_ip, endpoint=request.url.path)

        action = eval_result["action"]
        headers = eval_result.get("headers", {})

        if action == "BLOCK":
            return JSONResponse(
                status_code=403,
                content={
                    "error": "Forbidden",
                    "detail": eval_result["reason"],
                    "retry_after_seconds": eval_result.get("retry_after", 0),
                    "dos_protection": "ACTIVE",
                },
                headers=headers
            )

        if action == "THROTTLE":
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Too Many Requests",
                    "detail": eval_result["reason"],
                    "retry_after_seconds": eval_result.get("retry_after", 0),
                    "dos_protection": "ACTIVE",
                },
                headers=headers
            )

        # Action is ALLOW
        response = await call_next(request)
        for k, v in headers.items():
            response.headers[k] = v
        return response


# Module Singletons
default_dos_guard = DoSDefenseGuard()
default_tenant_limiter = TenantRateLimiter()
