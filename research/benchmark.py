"""
Benchmark model pembaca nota: akurasi + kecepatan + reliability + memori.

Contoh pemakaian (dari root project):
    python -m research.benchmark
    python -m research.benchmark --models qwen --runs 3
    python -m research.benchmark --models deepseek --runs 1

Hasil disimpan ke folder research/results/:
    predictions/<model>/<nota>.json
        -> output mentah & hasil parsing tiap nota

    runs.csv
        -> waktu inference dan status berhasil/gagal setiap run

    accuracy.csv
        -> metrik akurasi per model per nota

    summary.csv
        -> ringkasan akurasi, kecepatan, dan reliability per model

    environment.json
        -> spesifikasi komputer tempat benchmark dijalankan

RELIABILITY:
    run_success_rate
        Persentase seluruh inference yang berhasil menghasilkan Receipt
        yang dapat digunakan oleh pipeline.

    receipt_parse_rate
        Persentase receipt yang berhasil diparse minimal satu kali.

Accuracy tetap dihitung dari first successful result untuk setiap receipt.
Dengan demikian accuracy dan reliability dinilai secara terpisah.
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import platform
import time
from pathlib import Path

import pandas as pd
from PIL import Image

from modules.readers import ReaderError, create_reader
from modules.schema import Receipt

from .metrics import evaluate_receipt


ROOT = Path(__file__).resolve().parents[1]

SAMPLES_DIR = ROOT / "samples"

GT_DIR = (
    Path(__file__).resolve().parent
    / "ground_truth"
)

RESULTS_DIR = (
    Path(__file__).resolve().parent
    / "results"
)

ALL_MODELS = [
    "deepseek",
    "donut",
    "qwen",
]


def load_dataset() -> list[
    tuple[
        str,
        Image.Image,
        Receipt,
    ]
]:
    """Pasangkan gambar di samples/ dengan label di research/ground_truth/."""

    dataset = []

    for gt_path in sorted(
        GT_DIR.glob("*.json")
    ):
        image_path = next(
            (
                p
                for p in SAMPLES_DIR.glob(
                    f"{gt_path.stem}.*"
                )
                if p.suffix.lower()
                in {
                    ".jpg",
                    ".jpeg",
                    ".png",
                    ".webp",
                }
            ),
            None,
        )

        if image_path is None:
            print(
                f"[skip] gambar untuk "
                f"{gt_path.name} "
                "tidak ditemukan di samples/"
            )
            continue

        gt = Receipt.model_validate_json(
            gt_path.read_text()
        )

        dataset.append(
            (
                gt_path.stem,
                Image.open(image_path),
                gt,
            )
        )

    return dataset


def memory_mb() -> float:
    """RAM yang dipakai proses python saat ini (MB)."""

    import psutil

    return (
        psutil
        .Process(os.getpid())
        .memory_info()
        .rss
        / 1024**2
    )


def benchmark_model(
    model_key: str,
    dataset,
    runs: int,
) -> tuple[
    list[dict],
    list[dict],
    dict,
]:
    """Benchmark satu model terhadap seluruh dataset."""

    run_rows = []
    acc_rows = []

    mem_before = memory_mb()

    start = time.perf_counter()

    try:
        reader = create_reader(
            model_key
        )

    except (
        ReaderError,
        ImportError,
        OSError,
    ) as err:
        print(
            f"[{model_key}] "
            f"gagal load model: {err}"
        )

        return (
            [],
            [],
            {
                "model": model_key,
                "error": str(err),
            },
        )

    load_seconds = (
        time.perf_counter()
        - start
    )

    model_info = {
        "model": reader.label,
        "key": model_key,
        "load_seconds": round(
            load_seconds,
            2,
        ),
        "memory_mb_after_load": round(
            memory_mb()
            - mem_before,
            1,
        ),
        "device": getattr(
            reader,
            "device",
            "cloud API",
        ),
    }

    print(
        f"[{reader.label}] "
        f"load {load_seconds:.1f} detik "
        f"di {model_info['device']}"
    )

    out_dir = (
        RESULTS_DIR
        / "predictions"
        / model_key
    )

    out_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    for name, image, gt in dataset:
        first_result = None
        error = None

        successful_runs = 0

        for run in range(
            1,
            runs + 1,
        ):
            try:
                result = reader.read(
                    image
                )

            except ReaderError as err:
                error = str(err)

                print(
                    f"  {name} "
                    f"run {run}: "
                    f"ERROR {error[:120]}"
                )

                run_rows.append(
                    {
                        "model": reader.label,
                        "receipt": name,
                        "run": run,
                        "seconds": None,
                        "success": False,
                        "error": error,
                    }
                )

                continue

            successful_runs += 1

            print(
                f"  {name} "
                f"run {run}: "
                f"{result.seconds:.2f} detik"
            )

            run_rows.append(
                {
                    "model": reader.label,
                    "receipt": name,
                    "run": run,
                    "seconds": result.seconds,
                    "success": True,
                    "error": None,
                }
            )

            # Accuracy tetap dihitung dari
            # run pertama yang berhasil.
            first_result = (
                first_result
                or result
            )

        parsed = (
            first_result.parsed_receipt
            if first_result
            else None
        )

        metrics = evaluate_receipt(
            parsed,
            gt,
        )

        acc_rows.append(
            {
                "model": reader.label,
                "receipt": name,
                **metrics,
            }
        )

        # Simpan hasil prediction pertama yang berhasil.
        # Reliability seluruh run tetap tersimpan di runs.csv.
        (
            out_dir
            / f"{name}.json"
        ).write_text(
            json.dumps(
                {
                    "model": reader.label,
                    "receipt": name,
                    "error": (
                        None
                        if first_result
                        else error
                    ),
                    "raw_output": (
                        first_result.raw_output
                        if first_result
                        else None
                    ),
                    "parsed": (
                        parsed.model_dump()
                        if parsed
                        else None
                    ),
                    "run_summary": {
                        "total_runs": runs,
                        "successful_runs": successful_runs,
                        "failed_runs": (
                            runs
                            - successful_runs
                        ),
                        "success_rate": (
                            successful_runs
                            / runs
                        ),
                    },
                    "metrics": metrics,
                },
                indent=2,
                ensure_ascii=False,
            )
        )

    del reader

    gc.collect()

    return (
        run_rows,
        acc_rows,
        model_info,
    )


def environment_info() -> dict:
    """Informasi environment tempat benchmark dijalankan."""

    info = {
        "platform": platform.platform(),
        "processor": (
            platform.processor()
            or platform.machine()
        ),
        "python": platform.python_version(),
        "cpu_count": os.cpu_count(),
    }

    try:
        import psutil

        info["ram_gb"] = round(
            psutil.virtual_memory().total
            / 1024**3,
            1,
        )

    except ImportError:
        pass

    try:
        import torch

        info["torch"] = (
            torch.__version__
        )

        info["cuda"] = (
            torch.cuda.is_available()
        )

        info["mps"] = (
            torch.backends.mps.is_available()
        )

    except ImportError:
        pass

    return info


def summarize(
    runs_df: pd.DataFrame,
    acc_df: pd.DataFrame,
    models_info: list[dict],
) -> pd.DataFrame:
    """Gabungkan speed, accuracy, dan reliability menjadi satu summary."""

    # Compatibility untuk hasil benchmark lama yang belum
    # memiliki kolom success.
    runs_df = runs_df.copy()

    if "success" not in runs_df.columns:
        runs_df["success"] = (
            runs_df["error"].isna()
        )

    # -------------------------
    # SPEED
    # -------------------------
    speed = (
        runs_df
        .dropna(
            subset=["seconds"]
        )
        .groupby("model")["seconds"]
        .agg(
            first_run_s="first",
            mean_s="mean",
            min_s="min",
            max_s="max",
        )
    )

    # -------------------------
    # RUN RELIABILITY
    # -------------------------
    reliability = (
        runs_df
        .groupby("model")
        .agg(
            total_runs=(
                "success",
                "size",
            ),
            successful_runs=(
                "success",
                "sum",
            ),
        )
    )

    reliability[
        "failed_runs"
    ] = (
        reliability["total_runs"]
        - reliability["successful_runs"]
    )

    reliability[
        "run_success_rate"
    ] = (
        reliability["successful_runs"]
        / reliability["total_runs"]
    )

    # -------------------------
    # RECEIPT-LEVEL RELIABILITY
    # -------------------------
    receipt_reliability = (
        acc_df
        .groupby("model")["parsed"]
        .agg(
            total_receipts="size",
            parsed_receipts="sum",
        )
    )

    receipt_reliability[
        "failed_receipts"
    ] = (
        receipt_reliability[
            "total_receipts"
        ]
        - receipt_reliability[
            "parsed_receipts"
        ]
    )

    receipt_reliability[
        "receipt_parse_rate"
    ] = (
        receipt_reliability[
            "parsed_receipts"
        ]
        / receipt_reliability[
            "total_receipts"
        ]
    )

    # -------------------------
    # ACCURACY
    # -------------------------
    accuracy = (
        acc_df
        .groupby("model")
        .mean(
            numeric_only=True
        )
        .drop(
            columns=[
                "n_gt_items",
                "n_pred_items",
            ],
            errors="ignore",
        )
    )

    # -------------------------
    # MODEL INFO
    # -------------------------
    info = (
        pd.DataFrame(
            [
                model
                for model in models_info
                if "error"
                not in model
            ]
        )
        .set_index("model")
    )

    return (
        info
        .join(speed)
        .join(reliability)
        .join(receipt_reliability)
        .join(accuracy)
        .round(3)
        .reset_index()
    )


def run(
    models: list[str],
    runs: int,
) -> pd.DataFrame:
    """Jalankan benchmark melalui CLI."""

    from dotenv import load_dotenv

    load_dotenv(
        ROOT / ".env"
    )

    dataset = load_dataset()

    if not dataset:
        raise SystemExit(
            "Dataset kosong. "
            "Isi samples/ dan "
            "research/ground_truth/ dulu."
        )

    print(
        f"{len(dataset)} nota: "
        f"{[d[0] for d in dataset]}"
    )

    all_runs = []
    all_acc = []
    models_info = []

    for key in models:
        (
            run_rows,
            acc_rows,
            info,
        ) = benchmark_model(
            key,
            dataset,
            runs,
        )

        all_runs += run_rows
        all_acc += acc_rows

        models_info.append(
            info
        )

    return save_results(
        all_runs,
        all_acc,
        models_info,
    )


def save_results(
    all_runs: list[dict],
    all_acc: list[dict],
    models_info: list[dict],
) -> pd.DataFrame:
    """Simpan semua hasil benchmark ke CSV/JSON."""

    runs_df = pd.DataFrame(
        all_runs
    )

    acc_df = pd.DataFrame(
        all_acc
    )

    if runs_df.empty:
        raise SystemExit(
            "Tidak ada model yang "
            "berhasil dijalankan."
        )

    # Mendukung data benchmark lama yang belum
    # mempunyai field success.
    if "success" not in runs_df.columns:
        runs_df["success"] = (
            runs_df["error"].isna()
        )

    summary = summarize(
        runs_df,
        acc_df,
        models_info,
    )

    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    runs_df.to_csv(
        RESULTS_DIR
        / "runs.csv",
        index=False,
    )

    acc_df.to_csv(
        RESULTS_DIR
        / "accuracy.csv",
        index=False,
    )

    summary.to_csv(
        RESULTS_DIR
        / "summary.csv",
        index=False,
    )

    (
        RESULTS_DIR
        / "environment.json"
    ).write_text(
        json.dumps(
            {
                "machine": (
                    environment_info()
                ),
                "models": models_info,
            },
            indent=2,
        )
    )

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=(
            argparse.RawDescriptionHelpFormatter
        ),
    )

    parser.add_argument(
        "--models",
        nargs="+",
        default=ALL_MODELS,
        choices=ALL_MODELS,
    )

    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help=(
            "berapa kali tiap nota "
            "dibaca "
            "(untuk rata-rata waktu "
            "dan reliability)"
        ),
    )

    args = parser.parse_args()

    print(
        run(
            args.models,
            args.runs,
        ).to_string(
            index=False
        )
    )
