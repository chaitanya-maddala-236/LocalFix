from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "models"
MANIFEST = MODELS / "manifest.json"


def prepare(download: bool) -> None:
    try:
        from fastembed import TextEmbedding
    except ImportError as error:
        raise SystemExit("Install backend/requirements-local-ai.txt before preparing optional local models.") from error

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    model_name = manifest.get("local_services", {}).get("retrieval", {}).get("model_name", "BAAI/bge-small-en-v1.5")
    cache_dir = MODELS / "embeddings"
    if not download and not any(cache_dir.rglob("*.onnx")):
        raise SystemExit("Embedding files are missing. Run this command with --download while online.")
    encoder = TextEmbedding(
        model_name=model_name, cache_dir=str(cache_dir), local_files_only=not download,
        providers=["CPUExecutionProvider"], threads=2,
    )
    vector = next(iter(encoder.embed(["LocalFix offline model check"])))
    print(f"Embedding model ready: {model_name} ({len(vector)} dimensions)")

    asr_path = MODELS / "speech" / "tiny.en"
    if download:
        from huggingface_hub import snapshot_download

        snapshot_download(
            repo_id="Systran/faster-whisper-tiny.en", local_dir=str(asr_path),
            allow_patterns=["config.json", "model.bin", "tokenizer.json", "vocabulary.txt", "preprocessor_config.json"],
        )
    if not (asr_path / "model.bin").is_file():
        raise SystemExit(f"Local ASR weights are missing at {asr_path}. Run with --download while online.")
    from faster_whisper import WhisperModel

    WhisperModel(str(asr_path), device="cpu", compute_type="int8", cpu_threads=2, local_files_only=True)
    print(f"Local ASR model ready: {asr_path}")
    print("RapidOCR PP-OCRv6 weights are bundled in the installed RapidOCR wheel; runtime will load them locally.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prepare optional LocalFix CPU AI assets. Model download requires --download.")
    parser.add_argument("--download", action="store_true", help="Explicitly download model assets for later offline use.")
    prepare(parser.parse_args().download)
