"""Minimal hello-world demo for the FluxCapacitor async task system."""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running directly from the repo without installing the package.
REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

try:
    from rag2f.core.flux_capacitor import TaskManager
    from rag2f.core.flux_capacitor.queue import InMemoryTaskQueue
    from rag2f.core.flux_capacitor.store import InMemoryTaskStore
    from rag2f.core.morpheus.decorators.hook import hook
except ImportError as exc:
    print(
        "TaskManager/flux_capacitor not found. "
        "This hello world expects the async engine to be present."
    )
    print(f"Import error: {exc}")
    sys.exit(1)


class FakeMorpheus:
    """Small hook registry that matches the FluxCapacitor expectations."""

    def __init__(self) -> None:
        self.hooks: dict[str, list[object]] = {}

    def register(self, plugin_id: str, hook_obj: object) -> None:
        hook_obj.plugin_id = plugin_id
        self.hooks.setdefault(hook_obj.name, []).append(hook_obj)

    def resolve_hook(self, plugin_id: str, hook_name: str):
        for hook_obj in self.hooks.get(hook_name, []):
            if hook_obj.plugin_id == plugin_id:
                return hook_obj
        return None


class DummyRAG2F:
    """Minimal RAG2F surface required by FluxCapacitor."""

    def __init__(self, *, morpheus: FakeMorpheus) -> None:
        self.config_manager = None
        self.plugin_manager = morpheus


def _payload_meta(payload_ref: dict | None) -> dict:
    if not payload_ref:
        return {}
    meta = payload_ref.get("meta")
    return meta if isinstance(meta, dict) else {}


def main() -> int:
    saved_sentences: list[str] = []

    @hook("split_sentences")
    def split_sentences(*, payload_ref=None, context=None, **_):
        meta = _payload_meta(payload_ref)
        text = meta.get("text", "")
        sentences = [s.strip() for s in text.split(".") if s.strip()]
        print("[root] received: split_sentences")
        print(
            f"[root] split_sentences: {len(sentences)} sentences -> "
            f"spawning {len(sentences)} child jobs"
        )
        for index, sentence in enumerate(sentences, start=1):
            context.emit_child(
                "embed_sentence",
                payload_ref={
                    "repository": "demo",
                    "id": f"child-{index}",
                    "meta": {"sentence": sentence},
                },
            )

    @hook("embed_sentence")
    def embed_sentence(*, payload_ref=None, **_):
        meta = _payload_meta(payload_ref)
        sentence = meta.get("sentence", "")
        saved_sentences.append(sentence)
        print(f'[child] embed_sentence: "{sentence}" -> saved fake embedding')

    morpheus = FakeMorpheus()
    morpheus.register("flux_demo", split_sentences)
    morpheus.register("flux_demo", embed_sentence)

    rag2f = DummyRAG2F(morpheus=morpheus)
    task_manager = TaskManager(rag2f_instance=rag2f)

    store = InMemoryTaskStore()
    queue = InMemoryTaskQueue()
    task_manager.register_store("memory", store)
    task_manager.register_queue("memory", queue)
    task_manager.set_default_store("memory")
    task_manager.set_default_queue("memory")

    print("[hello] creating root job")
    root_task_id = task_manager.enqueue(
        plugin_id="flux_demo",
        hook="split_sentences",
        payload_ref={
            "repository": "demo",
            "id": "root",
            "meta": {
                "text": "Dario ha i capelli biondi. Dario ha gli occhi verdi.",
            },
        },
    )

    while task_manager.run_once():
        pass

    print(f"[done] root complete = {task_manager.is_tree_done(root_task_id)}")
    print(f"[done] saved sentences = {len(saved_sentences)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
