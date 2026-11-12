from __future__ import annotations

import asyncio
import concurrent.futures
import ipaddress
import shutil
import socket
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urlparse

from app.config import get_settings
from app.runtime.redaction import redact_secrets_in_text, sanitize_structured_payload, strip_untrusted_webpage_text


class BrowserSecurityError(PermissionError):
    """Raised when a URL violates SSRF, scheme, download, or domain allowlist rules."""


def _is_forbidden_ip(ip_obj: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return bool(
        ip_obj.is_private
        or ip_obj.is_loopback
        or ip_obj.is_link_local
        or ip_obj.is_multicast
        or ip_obj.is_reserved
        or ip_obj.is_unspecified
    )


def validate_browser_url(
    url: str,
    *,
    allowlist: list[str] | None = None,
    resolve_dns: bool = True,
) -> tuple[str, str]:
    """Validate URL scheme, credentials, domain allowlist, and SSRF IP safety.

    Returns (normalized_url, hostname).
    """
    raw = (url or "").strip()
    if not raw:
        raise BrowserSecurityError("URL cannot be empty")

    parsed = urlparse(raw)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise BrowserSecurityError(f"Blocked disallowed URL scheme: '{parsed.scheme}'")
    if parsed.username or parsed.password:
        raise BrowserSecurityError("Credentials embedded in URLs are forbidden")

    hostname = (parsed.hostname or "").strip().lower()
    if not hostname:
        raise BrowserSecurityError("URL is missing a valid hostname")

    if hostname in {"localhost", "localhost.localdomain", "metadata.google.internal"} or hostname.endswith(
        (".local", ".internal", ".localhost")
    ):
        raise BrowserSecurityError(f"Blocked internal/local hostname: '{hostname}'")

    # Reject literal forbidden IP addresses regardless of allowlist
    try:
        ip_literal = ipaddress.ip_address(hostname)
        if _is_forbidden_ip(ip_literal):
            raise BrowserSecurityError(f"Blocked private/loopback/metadata IP literal: '{hostname}'")
        if str(ip_literal).startswith("169.254."):
            raise BrowserSecurityError(f"Blocked cloud metadata IP: '{hostname}'")
    except ValueError:
        pass

    effective_allowlist = [
        d.strip().lower() for d in (allowlist if allowlist is not None else get_settings().playwright_allowlist) if d.strip()
    ]
    domain_allowed = any(hostname == domain or hostname.endswith(f".{domain}") for domain in effective_allowlist)
    if not domain_allowed:
        raise BrowserSecurityError(f"Domain '{hostname}' is not in the approved browser allowlist")

    if resolve_dns:
        try:
            infos = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80), proto=socket.IPPROTO_TCP)
        except socket.gaierror as exc:
            raise BrowserSecurityError(f"DNS resolution failed for '{hostname}': {exc}") from exc
        if not infos:
            raise BrowserSecurityError(f"No IP addresses resolved for '{hostname}'")
        for _, _, _, _, sockaddr in infos:
            resolved_ip = sockaddr[0]
            try:
                ip_obj = ipaddress.ip_address(resolved_ip.split("%")[0])
                if _is_forbidden_ip(ip_obj):
                    raise BrowserSecurityError(
                        f"SSRF blocked: '{hostname}' resolved to restricted IP '{resolved_ip}'"
                    )
            except ValueError as exc:
                raise BrowserSecurityError(f"Unparseable resolved IP '{resolved_ip}'") from exc

    return raw, hostname


def _run_in_worker_if_async(fn, *args, **kwargs):
    """Playwright Sync API raises inside an asyncio loop; dispatch cleanly on worker thread when needed."""
    try:
        asyncio.get_running_loop()
        in_async = True
    except RuntimeError:
        in_async = False

    if not in_async:
        return fn(*args, **kwargs)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(fn, *args, **kwargs).result()


class BrowserSessionManager:
    """Isolated, per-tenant ephemeral Playwright browser runtime for approved HR research.

    Guarantees:
    - Ephemeral incognito browser contexts (isolated cookies/storage per tenant + task).
    - Strict download prohibition (`accept_downloads=False` + download cancel handler).
    - Redirect-aware and subresource-aware `context.route("**/*", ...)` SSRF filter.
    - `<untrusted_webpage_content>` sanitization removing scripts, hidden DOM, and prompt injection text.
    """

    def __init__(self) -> None:
        self.settings = get_settings()

    def _session_dir(self, tenant_id: uuid.UUID, session_id: str) -> Path:
        root = (self.settings.browser_root_path / str(tenant_id) / session_id).resolve()
        tenant_root = (self.settings.browser_root_path / str(tenant_id)).resolve()
        if not root.is_relative_to(tenant_root):
            raise BrowserSecurityError("Invalid tenant browser session directory")
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _launch_browser(self, playwright):
        launch_errors: list[str] = []
        args = ["--disable-dev-shm-usage", "--no-first-run", "--disable-extensions"]
        for kwargs in (
            {"headless": self.settings.PLAYWRIGHT_HEADLESS, "args": args},
            {"headless": self.settings.PLAYWRIGHT_HEADLESS, "channel": "msedge", "args": args},
            {"headless": self.settings.PLAYWRIGHT_HEADLESS, "channel": "chrome", "args": args},
        ):
            try:
                return playwright.chromium.launch(**kwargs)
            except Exception as exc:
                launch_errors.append(f"{kwargs.get('channel', 'chromium')}: {exc}")
        raise RuntimeError("No Playwright Chromium/Edge/Chrome browser available: " + " | ".join(launch_errors))

    def _build_route_interceptor(
        self,
        *,
        allowlist: list[str],
        blocked_requests: list[dict[str, str]],
        resolve_dns: bool,
        route_mock_html: dict[str, str] | None = None,
    ):
        def handle_route(route) -> None:
            req = route.request
            req_url = req.url

            if route_mock_html and req_url in route_mock_html:
                route.fulfill(status=200, content_type="text/html; charset=utf-8", body=route_mock_html[req_url])
                return

            try:
                if req.is_navigation_request():
                    validate_browser_url(req_url, allowlist=allowlist, resolve_dns=resolve_dns)
                else:
                    parsed = urlparse(req_url)
                    if parsed.scheme.lower() not in {"http", "https"}:
                        raise BrowserSecurityError(f"Blocked subresource scheme: {parsed.scheme}")
                    host = (parsed.hostname or "").strip().lower()
                    if host in {"localhost"} or host.endswith((".local", ".internal")):
                        raise BrowserSecurityError(f"Blocked local subresource host: {host}")
                    try:
                        ip_obj = ipaddress.ip_address(host)
                        if _is_forbidden_ip(ip_obj):
                            raise BrowserSecurityError(f"Blocked subresource IP: {host}")
                    except ValueError:
                        pass
            except BrowserSecurityError as exc:
                blocked_requests.append({"url": redact_secrets_in_text(req_url, max_len=240), "reason": str(exc)})
                route.abort("blockedbyclient")
                return

            route.continue_()

        return handle_route

    def navigate_and_extract(
        self,
        *,
        tenant_id: uuid.UUID,
        url: str,
        allowlist: list[str] | None = None,
        capture_screenshot: bool = True,
        form_actions: list[dict[str, str]] | None = None,
        submit_selector: str | None = None,
        form_approved: bool = False,
        timeout_ms: int | None = None,
        resolve_dns: bool = True,
        route_mock_html: dict[str, str] | None = None,
        cleanup_session: bool = False,
    ) -> dict[str, Any]:
        eff_allowlist = allowlist if allowlist is not None else self.settings.playwright_allowlist
        normalized_url, hostname = validate_browser_url(
            url,
            allowlist=eff_allowlist,
            resolve_dns=(False if (route_mock_html and url in route_mock_html) else resolve_dns),
        )
        if form_actions and not form_approved:
            raise BrowserSecurityError("Form interaction requires explicit approval flag")

        return _run_in_worker_if_async(
            self._navigate_sync,
            tenant_id=tenant_id,
            url=normalized_url,
            hostname=hostname,
            allowlist=eff_allowlist,
            capture_screenshot=capture_screenshot,
            form_actions=form_actions or [],
            submit_selector=submit_selector,
            timeout_ms=int(timeout_ms or self.settings.PLAYWRIGHT_TIMEOUT_MS),
            resolve_dns=resolve_dns,
            route_mock_html=route_mock_html,
            cleanup_session=cleanup_session,
        )

    def _navigate_sync(
        self,
        *,
        tenant_id: uuid.UUID,
        url: str,
        hostname: str,
        allowlist: list[str],
        capture_screenshot: bool,
        form_actions: list[dict[str, str]],
        submit_selector: str | None,
        timeout_ms: int,
        resolve_dns: bool,
        route_mock_html: dict[str, str] | None,
        cleanup_session: bool,
    ) -> dict[str, Any]:
        from playwright.sync_api import sync_playwright

        session_id = f"brw-{uuid.uuid4().hex[:12]}"
        session_dir = self._session_dir(tenant_id, session_id)
        blocked_requests: list[dict[str, str]] = []
        blocked_downloads: list[str] = []
        t0 = time.perf_counter()

        try:
            with sync_playwright() as p:
                browser = self._launch_browser(p)
                context = browser.new_context(
                    accept_downloads=False,
                    ignore_https_errors=False,
                    java_script_enabled=True,
                    viewport={"width": 1280, "height": 800},
                )
                context.set_default_timeout(timeout_ms)
                context.route(
                    "**/*",
                    self._build_route_interceptor(
                        allowlist=allowlist,
                        blocked_requests=blocked_requests,
                        resolve_dns=resolve_dns,
                        route_mock_html=route_mock_html,
                    ),
                )
                page = context.new_page()

                def on_download(download) -> None:
                    blocked_downloads.append(download.suggested_filename)
                    try:
                        download.cancel()
                    except Exception:
                        pass

                page.on("download", on_download)

                response = page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                final_url = page.url

                # Re-verify final URL after any client-side/meta redirect
                validate_browser_url(
                    final_url,
                    allowlist=allowlist,
                    resolve_dns=(False if (route_mock_html and final_url in route_mock_html) else resolve_dns),
                )

                form_results: list[dict[str, str]] = []
                for action in form_actions:
                    selector = str(action.get("selector", "")).strip()
                    value = str(action.get("value", ""))
                    if selector:
                        page.fill(selector, value, timeout=min(timeout_ms, 5000))
                        form_results.append({"selector": selector, "status": "filled"})
                if submit_selector:
                    page.click(submit_selector, timeout=min(timeout_ms, 5000))
                    page.wait_for_load_state("domcontentloaded", timeout=min(timeout_ms, 5000))
                    form_results.append({"selector": submit_selector, "status": "clicked"})
                    validate_browser_url(
                        page.url,
                        allowlist=allowlist,
                        resolve_dns=(False if (route_mock_html and page.url in route_mock_html) else resolve_dns),
                    )

                extracted = page.evaluate(
                    """() => {
                        const cloned = document.body ? document.body.cloneNode(true) : null;
                        if (cloned) {
                            cloned.querySelectorAll('script, style, noscript, iframe, [hidden], [aria-hidden="true"]').forEach(el => el.remove());
                        }
                        const links = Array.from(document.querySelectorAll('a[href]')).slice(0, 15).map(a => ({
                            text: (a.innerText || '').trim().slice(0, 120),
                            href: a.href
                        }));
                        return {
                            title: document.title || '',
                            text: cloned ? (cloned.innerText || '').trim() : '',
                            links
                        };
                    }"""
                )

                screenshot_path: str | None = None
                if capture_screenshot:
                    shot_file = session_dir / "screenshot.png"
                    page.screenshot(path=str(shot_file), full_page=False)
                    screenshot_path = str(shot_file)

                duration_ms = round((time.perf_counter() - t0) * 1000)
                status_code = response.status if response else 200
                wrapped_text = strip_untrusted_webpage_text(
                    extracted.get("text", ""),
                    source_url=page.url,
                    max_chars=6000,
                )

                context.close()
                browser.close()

                return {
                    "ok": True,
                    "session_id": session_id,
                    "tenant_id": str(tenant_id),
                    "requested_url": url,
                    "final_url": page.url,
                    "hostname": hostname,
                    "status_code": status_code,
                    "title": redact_secrets_in_text(extracted.get("title", ""), max_len=200),
                    "content": wrapped_text,
                    "links": sanitize_structured_payload(extracted.get("links", [])[:10]),
                    "form_actions_applied": form_results,
                    "screenshot_path": screenshot_path,
                    "blocked_requests": blocked_requests,
                    "blocked_downloads": blocked_downloads,
                    "duration_ms": duration_ms,
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                    "isolation": {
                        "ephemeral_context": True,
                        "accept_downloads": False,
                        "cookies_persisted": False,
                        "allowlist_enforced": True,
                    },
                }
        finally:
            if cleanup_session and session_dir.exists():
                shutil.rmtree(session_dir, ignore_errors=True)

    def search_recruitment_info(
        self,
        *,
        tenant_id: uuid.UUID,
        query: str,
        target_urls: list[str] | None = None,
        allowlist: list[str] | None = None,
        route_mock_html: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Visit approved recruitment URLs (or default approved search page) and collect sanitized results."""
        eff_allowlist = allowlist if allowlist is not None else self.settings.playwright_allowlist
        candidate_urls = list(target_urls or [])
        if not candidate_urls:
            q = quote_plus(query.strip() or "software engineer hiring requirements")
            candidate_urls = [f"https://www.wikipedia.org/w/index.php?search={q}"]

        visited: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        for target in candidate_urls[:3]:
            try:
                res = self.navigate_and_extract(
                    tenant_id=tenant_id,
                    url=target,
                    allowlist=eff_allowlist,
                    capture_screenshot=True,
                    route_mock_html=route_mock_html,
                )
                visited.append(res)
            except BrowserSecurityError:
                raise
            except Exception as exc:
                errors.append({"url": target, "error": redact_secrets_in_text(str(exc), max_len=240)})

        return {
            "ok": len(visited) > 0,
            "query": query,
            "visited_pages": visited,
            "errors": errors,
            "status": "completed" if visited else "failed",
        }


browser_manager = BrowserSessionManager()
