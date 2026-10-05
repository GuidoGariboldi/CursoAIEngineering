"""Script de validación: hace la misma pregunta en modo normal y en streaming.

    python main.py                           # usa el proveedor de LLM_PROVIDER
    python main.py gemini openai anthropic   # prueba los proveedores indicados
"""

import asyncio
import sys

from dotenv import load_dotenv

from llm_client import AsyncLLMManager, ChatMessage, ConfigurationError, GenerationConfig

PREGUNTA = "¿Qué es la entropía?"


async def probar(provider: str | None) -> None:
    try:
        llm = AsyncLLMManager(provider)
    except ConfigurationError as exc:
        print(f"\n[config] {exc}")
        return

    messages = [
        ChatMessage(role="system", content="Respondé en español, en no más de tres oraciones."),
        ChatMessage(role="user", content=PREGUNTA),
    ]
    config = GenerationConfig(temperature=0.3, max_tokens=1000)

    async with llm:
        print(f"\n===== {llm.provider.value} ({llm.model}) =====")

        print("\n--- Modo normal ---")
        resp = await llm.generate(messages, config)
        if resp.ok:
            print(resp.content)
            if resp.usage:
                print(f"[tokens: {resp.usage.input_tokens} entrada / {resp.usage.output_tokens} salida]")
        else:
            print(f"[error controlado] {resp.error.type.value}: {resp.error.message}")

        print("\n--- Modo streaming ---")
        async for chunk in llm.stream(messages, config):
            if chunk.ok:
                print(chunk.content, end="", flush=True)
            else:
                print(f"\n[error controlado] {chunk.error.type.value}: {chunk.error.message}")
        print()


async def main() -> None:
    load_dotenv()
    providers = sys.argv[1:] or [None]  # None = lo que diga LLM_PROVIDER
    for provider in providers:
        await probar(provider)


if __name__ == "__main__":
    asyncio.run(main())
