from dataclasses import dataclass
import json
import os
import re
from typing import Any, Callable, Optional

from app.config import get_settings

from .guardrails import sanitize_outbound_llm_context
from .optimizer import (
    count_tokens,
    estimate_cost_usd,
    get_current_optimizer_scope,
    prepare_optimized_llm_request,
    tenant_response_cache,
)


@dataclass
class LLMGenerationResult:
    content: str
    parsed_json: Optional[dict[str, Any]]
    provider_used: str
    model_used: str
    input_tokens: int
    cached_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    baseline_input_tokens: int = 0
    optimization_enabled: bool = True
    optimization_methods_used: Optional[list[str]] = None
    model_tier_selected: str = "tier_0_rule"
    cache_hit: bool = False
    fallback_reason: str = ""


class ConfigurableLLMProvider:
    """
    Provider-agnostic LLM adapter supporting Google Gemini, OpenAI, Anthropic,
    or deterministic structured synthesis when no external API key is configured.
    """

    def resolve_provider(self, override_provider: Optional[str] = None) -> str:
        settings = get_settings()
        pref = (override_provider or settings.LLM_PROVIDER or "auto").strip().lower()
        if pref == "deterministic":
            return "deterministic"
        if pref == "gemini" and settings.GEMINI_API_KEY:
            return "gemini"
        if pref == "openai" and settings.OPENAI_API_KEY:
            return "openai"
        if pref == "anthropic" and settings.ANTHROPIC_API_KEY:
            return "anthropic"
        if pref == "auto":
            if settings.GEMINI_API_KEY and not settings.GEMINI_API_KEY.startswith("your_"):
                return "gemini"
            if settings.OPENAI_API_KEY and not settings.OPENAI_API_KEY.startswith("sk-your"):
                return "openai"
            if settings.ANTHROPIC_API_KEY and not settings.ANTHROPIC_API_KEY.startswith("sk-ant-your"):
                return "anthropic"
        return "deterministic"

    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        context_data: dict[str, Any],
        fallback_fn: Callable[[dict[str, Any]], dict[str, Any]],
        provider_override: Optional[str] = None,
        model_override: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 1200,
    ) -> LLMGenerationResult:
        provider = self.resolve_provider(provider_override)
        settings = get_settings()
        scope = get_current_optimizer_scope()

        workflow_slug = (scope.get("workflow_slug") if scope else None) or "hr-general"
        tenant_id = (scope.get("tenant_id") if scope else None) or ""
        actor_role = (scope.get("actor_role") if scope else None) or "business_admin"
        blind_mode = bool(scope.get("blind_screening_mode", False)) if scope else False
        strict_pii = bool(scope.get("strict_pii_masking", False)) if scope else False
        opt_enabled = (
            bool(scope.get("optimization_enabled", settings.ENABLE_CONTEXT_OPTIMIZATION))
            if scope is not None
            else settings.ENABLE_CONTEXT_OPTIMIZATION
        )
        tier_override = scope.get("model_tier_override") if scope else None

        safe_sys, safe_user, safe_ctx, guard_flags = sanitize_outbound_llm_context(
            system_prompt,
            user_prompt,
            context_data,
            blind_mode=blind_mode,
            strict_pii_masking=strict_pii,
        )

        opt_sys, opt_user, opt_ctx, opt_meta = prepare_optimized_llm_request(
            system_prompt=safe_sys,
            user_prompt=safe_user,
            context_data=safe_ctx,
            provider=provider,
            workflow_slug=workflow_slug,
            optimization_enabled=opt_enabled,
            model_tier_override=tier_override,
            explicit_model=model_override or settings.LLM_DEFAULT_MODEL or None,
        )

        baseline_tok = int(opt_meta["baseline_input_tokens"])
        opt_in_tok = int(opt_meta["optimized_input_tokens"])
        methods_used = list(opt_meta["methods_used"])
        selected_tier = str(opt_meta["model_tier"])
        selected_model = str(opt_meta["selected_model"])

        def _commit_scope(res: LLMGenerationResult) -> LLMGenerationResult:
            if scope is not None:
                scope["baseline_input_tokens"] = int(scope.get("baseline_input_tokens", 0)) + res.baseline_input_tokens
                scope["optimized_input_tokens"] = int(scope.get("optimized_input_tokens", 0)) + res.input_tokens
                scope["cached_tokens"] = int(scope.get("cached_tokens", 0)) + res.cached_tokens
                scope["model_tier_selected"] = res.model_tier_selected
                scope["cache_hit"] = bool(scope.get("cache_hit") or res.cache_hit)
                if res.fallback_reason:
                    scope["llm_fallback_reason"] = res.fallback_reason
                existing_methods = list(scope.get("optimization_methods_used") or [])
                for m in res.optimization_methods_used or []:
                    if m not in existing_methods:
                        existing_methods.append(m)
                scope["optimization_methods_used"] = existing_methods
                existing_flags = list(scope.get("guardrail_flags") or [])
                for fl in guard_flags:
                    if fl not in existing_flags:
                        existing_flags.append(fl)
                if res.fallback_reason and "llm_provider_fallback" not in existing_flags:
                    existing_flags.append("llm_provider_fallback")
                scope["guardrail_flags"] = existing_flags
            return res

        cache_key = ""
        can_cache = bool(opt_enabled and settings.ENABLE_RESPONSE_CACHE and opt_meta.get("cacheable") and tenant_id)
        if can_cache:
            cache_key = tenant_response_cache.build_key(
                tenant_id=tenant_id,
                actor_role=actor_role,
                workflow_slug=workflow_slug,
                blind_mode=blind_mode,
                system_prompt=opt_sys,
                user_prompt=opt_user,
                context_data=opt_ctx,
            )
            cached_entry = tenant_response_cache.get(cache_key)
            if cached_entry is not None:
                return _commit_scope(
                    LLMGenerationResult(
                        content=cached_entry["content"],
                        parsed_json=cached_entry["parsed_json"],
                        provider_used=f"{provider}_cached",
                        model_used=cached_entry.get("model_used", selected_model),
                        input_tokens=0,
                        cached_tokens=opt_in_tok,
                        output_tokens=int(cached_entry.get("output_tokens", 0)),
                        estimated_cost_usd=0.0,
                        baseline_input_tokens=baseline_tok,
                        optimization_enabled=opt_enabled,
                        optimization_methods_used=list(dict.fromkeys(methods_used + ["tenant_response_cache"])),
                        model_tier_selected=selected_tier,
                        cache_hit=True,
                    )
                )

        fallback_reason = ""
        if provider != "deterministic":
            try:
                raw_text, model_used, in_tok, out_tok = self._invoke_live_provider(
                    provider=provider,
                    model_override=selected_model,
                    system_prompt=opt_sys,
                    user_prompt=opt_user,
                    context_data=opt_ctx,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                parsed = self._extract_json(raw_text)
                if parsed is not None:
                    actual_in = in_tok or opt_in_tok
                    actual_out = out_tok or max(40, count_tokens(raw_text))
                    cost = estimate_cost_usd(
                        model_used,
                        actual_in,
                        actual_out,
                        cached_tokens=0,
                        provider_used=provider,
                    )
                    if can_cache and cache_key:
                        tenant_response_cache.set(
                            cache_key,
                            {
                                "content": raw_text,
                                "parsed_json": parsed,
                                "model_used": model_used,
                                "output_tokens": actual_out,
                            },
                        )
                    return _commit_scope(
                        LLMGenerationResult(
                            content=raw_text,
                            parsed_json=parsed,
                            provider_used=provider,
                            model_used=model_used,
                            input_tokens=actual_in,
                            cached_tokens=0,
                            output_tokens=actual_out,
                            estimated_cost_usd=cost,
                            baseline_input_tokens=max(actual_in, baseline_tok) if opt_enabled else actual_in,
                            optimization_enabled=opt_enabled,
                            optimization_methods_used=methods_used,
                            model_tier_selected=selected_tier,
                            cache_hit=False,
                        )
                    )
                fallback_reason = f"{provider}: unparseable_structured_response"
            except Exception as exc:
                # Fall through with redacted telemetry if external LLM fails or times out
                fallback_reason = re.sub(
                    r"(sk-[A-Za-z0-9_-]{8,}|AIza[0-9A-Za-z_-]{12,}|Bearer\s+\S+|https?://[^/\s]+:[^@\s]+@)",
                    "[REDACTED]",
                    f"{provider} {type(exc).__name__}: {exc}",
                )[:220]

        fallback_data = fallback_fn(opt_ctx)
        serialized = json.dumps(fallback_data, default=str)
        out_tok = max(48, count_tokens(serialized))
        model_label = selected_model or "deterministic-hr-synthesizer-v1"
        if can_cache and cache_key and not fallback_reason:
            tenant_response_cache.set(
                cache_key,
                {
                    "content": serialized,
                    "parsed_json": fallback_data,
                    "model_used": model_label,
                    "output_tokens": out_tok,
                },
            )
        return _commit_scope(
            LLMGenerationResult(
                content=serialized,
                parsed_json=fallback_data,
                provider_used="deterministic_fallback_on_error" if fallback_reason else "deterministic_offline",
                model_used=model_label,
                input_tokens=opt_in_tok,
                cached_tokens=0,
                output_tokens=out_tok,
                estimated_cost_usd=0.0,
                baseline_input_tokens=baseline_tok,
                optimization_enabled=opt_enabled,
                optimization_methods_used=methods_used,
                model_tier_selected="tier_0_rule",
                cache_hit=False,
                fallback_reason=fallback_reason,
            )
        )

    def _invoke_live_provider(
        self,
        *,
        provider: str,
        model_override: str,
        system_prompt: str,
        user_prompt: str,
        context_data: dict[str, Any],
        temperature: float,
        max_tokens: int,
    ) -> tuple[str, str, int, int]:
        settings = get_settings()
        combined_user = (
            f"USER REQUEST:\n{user_prompt}\n\n"
            f"VERIFIED TENANT CONTEXT & TOOL OUTPUTS (JSON):\n{json.dumps(context_data, default=str)[:9000]}\n\n"
            "Respond ONLY with valid JSON matching the specialized agent output schema."
        )

        if provider == "gemini":
            from google import genai
            from google.genai import types

            model_name = model_override or "gemini-2.5-flash"
            client = genai.Client(api_key=settings.GEMINI_API_KEY)
            resp = client.models.generate_content(
                model=model_name,
                contents=combined_user,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                    response_mime_type="application/json",
                ),
            )
            usage = getattr(resp, "usage_metadata", None)
            in_tok = int(getattr(usage, "prompt_token_count", 0) or 0)
            out_tok = int(getattr(usage, "candidates_token_count", 0) or 0)
            return resp.text or "{}", model_name, in_tok, out_tok

        if provider == "openai":
            from openai import OpenAI

            model_name = model_override or "gpt-4o-mini"
            client = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=settings.LLM_TIMEOUT_SECONDS)
            resp = client.chat.completions.create(
                model=model_name,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": combined_user},
                ],
            )
            text = resp.choices[0].message.content or "{}"
            in_tok = int(getattr(resp.usage, "prompt_tokens", 0) or 0)
            out_tok = int(getattr(resp.usage, "completion_tokens", 0) or 0)
            return text, model_name, in_tok, out_tok

        if provider == "anthropic":
            from anthropic import Anthropic

            model_name = model_override or "claude-3-5-haiku-latest"
            client = Anthropic(api_key=settings.ANTHROPIC_API_KEY, timeout=settings.LLM_TIMEOUT_SECONDS)
            resp = client.messages.create(
                model=model_name,
                system=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": combined_user}],
            )
            text = "".join(getattr(block, "text", "") for block in resp.content)
            in_tok = int(getattr(resp.usage, "input_tokens", 0) or 0)
            out_tok = int(getattr(resp.usage, "output_tokens", 0) or 0)
            return text, model_name, in_tok, out_tok

        raise ValueError(f"Unsupported LLM provider: {provider}")

    @staticmethod
    def _extract_json(raw_text: str) -> Optional[dict[str, Any]]:
        cleaned = raw_text.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        try:
            obj = json.loads(cleaned)
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None


llm_provider = ConfigurableLLMProvider()
