"""
LLM Backend Abstraction Layer
==============================
Pluggable backends for language-model inference inside SYSGrow.

Supported backends
------------------
* **OpenAIBackend** — ChatGPT / GPT-4o-mini via the ``openai`` SDK.
* **AnthropicBackend** — Claude 3.5 Haiku / Sonnet via the ``anthropic`` SDK.
* **LocalTransformersBackend** — Any HuggingFace causal-LM, optimised for
  small models such as **EXAONE 4.0 1.2B** that can run on a Raspberry Pi
  or modest GPU.

All heavy dependencies (``openai``, ``anthropic``, ``torch``,
``transformers``) are imported lazily so the module never breaks at
import time when a particular SDK is missing.

Quick-start
-----------
::

    from app.services.ai.llm_backends import OpenAIBackend

    backend = OpenAIBackend(api_key="sk-...", model="gpt-4o-mini")
    if backend.initialize():
        reply = backend.generate(
            system_prompt="You are a plant care expert.",
            user_prompt="My tomato leaves are yellowing.",
        )
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class LLMResponse:
    """Standardised wrapper around every backend response."""

    text: str
    model: str
    usage: dict[str, int] = field(default_factory=dict)  # prompt_tokens, completion_tokens, total_tokens
    latency_ms: float = 0.0
    raw: Any = None  # backend-specific raw response object


# ---------------------------------------------------------------------------
# Abstract backend
# ---------------------------------------------------------------------------


class LLMBackend(ABC):
    """
    Abstract base for every LLM backend.

    Subclasses must implement :meth:`initialize`, :meth:`generate`,
    :attr:`name` and :attr:`is_available`.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier for this backend (e.g. ``"openai"``)."""

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """``True`` when the backend has been initialised and is ready."""

    @abstractmethod
    def initialize(self) -> bool:
        """
        Perform one-time setup (load model, validate API key, …).

        Returns ``True`` on success.
        """

    @abstractmethod
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_tokens: int = 512,
        temperature: float = 0.3,
        json_mode: bool = False,
    ) -> LLMResponse:
        """
        Generate a text completion.

        Parameters
        ----------
        system_prompt:
            Role / persona instruction.
        user_prompt:
            The concrete request.
        max_tokens:
            Upper-bound on generated tokens.
        temperature:
            Sampling temperature (0 = deterministic).
        json_mode:
            Hint the backend to return valid JSON (not all backends
            support this natively).

        Returns
        -------
        LLMResponse
        """

    # -- helpers available to all backends ----------------------------------

    def _timed(self, fn, *args, **kwargs):
        """Call *fn* and return ``(result, elapsed_ms)``."""
        t0 = time.perf_counter()
        result = fn(*args, **kwargs)
        return result, (time.perf_counter() - t0) * 1000


# ---------------------------------------------------------------------------
# OpenAI backend  (ChatGPT / GPT-4o-mini)
# ---------------------------------------------------------------------------


class OpenAIBackend(LLMBackend):
    """
    Backend for OpenAI's Chat Completions API.

    Requires the ``openai`` package (``pip install openai``).

    Parameters
    ----------
    api_key:
        OpenAI API key.
    model:
        Model identifier (default ``gpt-4o-mini``).
    base_url:
        Optional custom endpoint (e.g. Azure OpenAI or compatible proxy).
    timeout:
        Request timeout in seconds.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str | None = None,
        timeout: int = 30,
    ):
        self._api_key = api_key
        self._model = model
        self._base_url = base_url
        self._timeout = timeout
        self._client: Any = None

    # -- ABC ----------------------------------------------------------------

    @property
    def name(self) -> str:
        return "openai"

    @property
    def is_available(self) -> bool:
        return self._client is not None

    def initialize(self) -> bool:
        if not self._api_key:
            logger.warning("OpenAI backend: no API key provided")
            return False
        try:
            import openai

            kwargs: dict[str, Any] = {
                "api_key": self._api_key,
                "timeout": self._timeout,
            }
            if self._base_url:
                kwargs["base_url"] = self._base_url
            self._client = openai.OpenAI(**kwargs)
            # Quick validation — list models would fail on bad key
            logger.info("OpenAI backend initialised (model=%s)", self._model)
            return True
        except ImportError:
            logger.error("OpenAI backend: 'openai' package not installed.  Run: pip install openai")
        except Exception as exc:
            logger.error("OpenAI backend init failed: %s", exc)
        return False

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_tokens: int = 512,
        temperature: float = 0.3,
        json_mode: bool = False,
    ) -> LLMResponse:
        if not self.is_available:
            raise RuntimeError("OpenAI backend not initialised")

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        response, latency = self._timed(self._client.chat.completions.create, **kwargs)

        usage = {}
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        return LLMResponse(
            text=response.choices[0].message.content or "",
            model=response.model,
            usage=usage,
            latency_ms=latency,
            raw=response,
        )


# ---------------------------------------------------------------------------
# Anthropic backend  (Claude)
# ---------------------------------------------------------------------------


class AnthropicBackend(LLMBackend):
    """
    Backend for Anthropic's Messages API.

    Requires the ``anthropic`` package (``pip install anthropic``).

    Parameters
    ----------
    api_key:
        Anthropic API key.
    model:
        Model identifier (default ``claude-3-5-haiku-latest``).
    timeout:
        Request timeout in seconds.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "claude-3-5-haiku-latest",
        timeout: int = 30,
    ):
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._client: Any = None

    # -- ABC ----------------------------------------------------------------

    @property
    def name(self) -> str:
        return "anthropic"

    @property
    def is_available(self) -> bool:
        return self._client is not None

    def initialize(self) -> bool:
        if not self._api_key:
            logger.warning("Anthropic backend: no API key provided")
            return False
        try:
            import anthropic

            self._client = anthropic.Anthropic(
                api_key=self._api_key,
                timeout=self._timeout,
            )
            logger.info("Anthropic backend initialised (model=%s)", self._model)
            return True
        except ImportError:
            logger.error("Anthropic backend: 'anthropic' package not installed.  Run: pip install anthropic")
        except Exception as exc:
            logger.error("Anthropic backend init failed: %s", exc)
        return False

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_tokens: int = 512,
        temperature: float = 0.3,
        json_mode: bool = False,
    ) -> LLMResponse:
        if not self.is_available:
            raise RuntimeError("Anthropic backend not initialised")

        # Anthropic uses 'system' as a top-level param, not in messages
        prompt = user_prompt
        if json_mode:
            prompt += "\n\nRespond ONLY with valid JSON, no markdown fences."

        response, latency = self._timed(
            self._client.messages.create,
            model=self._model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}],
        )

        text = ""
        if response.content:
            text = response.content[0].text

        usage = {}
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": (response.usage.input_tokens + response.usage.output_tokens),
            }

        return LLMResponse(
            text=text,
            model=response.model,
            usage=usage,
            latency_ms=latency,
            raw=response,
        )


# ---------------------------------------------------------------------------
# Local HuggingFace Transformers backend  (EXAONE 4.0 1.2B etc.)
# ---------------------------------------------------------------------------


class LocalTransformersBackend(LLMBackend):
    """
    Backend for locally-hosted HuggingFace causal language models.

    Ideal for small models like **EXAONE 4.0 1.2B** that fit in RAM on
    a Raspberry Pi 5 (8 GB) or a modest GPU.

    Requires ``torch`` and ``transformers``::

        pip install torch transformers

    Parameters
    ----------
    model_path:
        HuggingFace model ID (``"LGAI-EXAONE/EXAONE-4.0-1.2B-Instruct"``)
        or local directory containing model weights.
    device:
        ``"cpu"``, ``"cuda"``, ``"cuda:0"``, ``"mps"``, or ``"auto"``.
    quantize:
        Apply 4-bit quantisation via ``bitsandbytes`` to reduce memory.
        Requires ``pip install bitsandbytes``.
    torch_dtype:
        Data type for model weights (``"float16"``, ``"bfloat16"``,
        ``"float32"``).  Default ``"float16"`` for memory efficiency.
    max_model_len:
        Maximum context length to allocate.
    """

    def __init__(
        self,
        model_path: str = "LGAI-EXAONE/EXAONE-4.0-1.2B-Instruct",
        device: str = "auto",
        quantize: bool = False,
        torch_dtype: str = "float16",
        max_model_len: int = 4096,
    ):
        self._model_path = model_path
        self._device = device
        self._quantize = quantize
        self._torch_dtype = torch_dtype
        self._max_model_len = max_model_len
        self._model: Any = None
        self._tokenizer: Any = None

    # -- ABC ----------------------------------------------------------------

    @property
    def name(self) -> str:
        return "local"

    @property
    def is_available(self) -> bool:
        return self._model is not None and self._tokenizer is not None

    def initialize(self) -> bool:
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer

            logger.info(
                "Loading local model %s (device=%s, quantize=%s) …",
                self._model_path,
                self._device,
                self._quantize,
            )

            dtype_map = {
                "float16": torch.float16,
                "bfloat16": torch.bfloat16,
                "float32": torch.float32,
            }
            torch_dtype = dtype_map.get(self._torch_dtype, torch.float16)

            self._tokenizer = AutoTokenizer.from_pretrained(
                self._model_path,
                trust_remote_code=True,
            )
            if self._tokenizer.pad_token is None:
                self._tokenizer.pad_token = self._tokenizer.eos_token

            model_kwargs: dict[str, Any] = {
                "torch_dtype": torch_dtype,
                "trust_remote_code": True,
            }

            if self._quantize:
                try:
                    from transformers import BitsAndBytesConfig

                    model_kwargs["quantization_config"] = BitsAndBytesConfig(
                        load_in_4bit=True,
                        bnb_4bit_compute_dtype=torch_dtype,
                        bnb_4bit_quant_type="nf4",
                    )
                    logger.info("4-bit quantisation enabled via bitsandbytes")
                except ImportError:
                    logger.warning(
                        "bitsandbytes not installed — loading without quantisation.  Run: pip install bitsandbytes"
                    )

            if self._device == "auto":
                model_kwargs["device_map"] = "auto"
            else:
                model_kwargs["device_map"] = {"": self._device}

            self._model = AutoModelForCausalLM.from_pretrained(
                self._model_path,
                **model_kwargs,
            )
            self._model.eval()

            logger.info(
                "✓ Local model loaded: %s (dtype=%s)",
                self._model_path,
                torch_dtype,
            )
            return True

        except ImportError as exc:
            logger.error(
                "Local model backend: missing dependency — %s.  Run: pip install torch transformers",
                exc,
            )
        except Exception as exc:
            logger.error("Local model init failed: %s", exc)
        return False

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_tokens: int = 512,
        temperature: float = 0.3,
        json_mode: bool = False,
    ) -> LLMResponse:
        if not self.is_available:
            raise RuntimeError("Local model backend not initialised")

        import torch

        prompt = user_prompt
        if json_mode:
            prompt += "\n\nRespond ONLY with valid JSON."

        # Build chat-template messages (works with EXAONE Instruct and
        # most HuggingFace chat models)
        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]

        try:
            input_text = self._tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )
        except Exception:
            # Fallback for models without chat template
            input_text = f"### System:\n{system_prompt}\n\n### User:\n{prompt}\n\n### Assistant:\n"

        inputs = self._tokenizer(
            input_text,
            return_tensors="pt",
            truncation=True,
            max_length=self._max_model_len,
        )
        device = next(self._model.parameters()).device
        inputs = {k: v.to(device) for k, v in inputs.items()}
        input_len = inputs["input_ids"].shape[1]

        gen_kwargs: dict[str, Any] = {
            "max_new_tokens": max_tokens,
            "do_sample": temperature > 0,
            "pad_token_id": self._tokenizer.pad_token_id,
        }
        if temperature > 0:
            gen_kwargs["temperature"] = temperature
            gen_kwargs["top_p"] = 0.9

        with torch.no_grad():
            outputs, latency = self._timed(
                self._model.generate,
                **inputs,
                **gen_kwargs,
            )

        new_tokens = outputs[0][input_len:]
        text = self._tokenizer.decode(new_tokens, skip_special_tokens=True).strip()

        return LLMResponse(
            text=text,
            model=self._model_path,
            usage={
                "prompt_tokens": input_len,
                "completion_tokens": len(new_tokens),
                "total_tokens": input_len + len(new_tokens),
            },
            latency_ms=latency,
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_backend(
    provider: str,
    *,
    api_key: str = "",
    model: str = "",
    base_url: str | None = None,
    local_model_path: str = "",
    local_device: str = "auto",
    local_quantize: bool = False,
    local_torch_dtype: str = "float16",
    timeout: int = 30,
) -> LLMBackend | None:
    """
    Factory: create and initialise the right backend from a provider name.

    Parameters
    ----------
    provider:
        One of ``"openai"``, ``"anthropic"``, ``"local"``, or ``"none"``.

    Returns
    -------
    An initialised :class:`LLMBackend`, or ``None`` if the provider is
    ``"none"`` or initialisation fails.
    """
    provider = provider.strip().lower()

    if provider in ("none", ""):
        logger.info("LLM provider set to 'none' — LLM features disabled")
        return None

    backend: LLMBackend | None = None

    if provider == "openai":
        backend = OpenAIBackend(
            api_key=api_key,
            model=model or "gpt-4o-mini",
            base_url=base_url,
            timeout=timeout,
        )
    elif provider == "anthropic":
        backend = AnthropicBackend(
            api_key=api_key,
            model=model or "claude-3-5-haiku-latest",
            timeout=timeout,
        )
    elif provider == "local":
        backend = LocalTransformersBackend(
            model_path=local_model_path or "LGAI-EXAONE/EXAONE-4.0-1.2B-Instruct",
            device=local_device,
            quantize=local_quantize,
            torch_dtype=local_torch_dtype,
            max_model_len=4096,
        )
    else:
        logger.error("Unknown LLM provider '%s'", provider)
        return None

    if backend.initialize():
        return backend

    logger.warning(
        "LLM backend '%s' failed to initialise — LLM features disabled",
        provider,
    )
    return None
