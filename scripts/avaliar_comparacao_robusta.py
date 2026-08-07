#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Avaliacao comum da comparacao operacional e da ablacao de descoberta.

O script nao usa texto dos chamados. Ele cruza apenas atribuicoes por chave
dentro do ambiente privado, publica agregados e gera um ledger pseudonimizado.
Sala de Sigilo e casos de escopo indeterminado ja devem ter sido removidos
antes do Stage 3 e sao recusados se reaparecerem.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import hmac
import json
import math
import os
import secrets
import statistics
import unicodedata
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime
from itertools import combinations
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment
from sklearn.metrics import (
    adjusted_mutual_info_score,
    adjusted_rand_score,
    completeness_score,
    fowlkes_mallows_score,
    homogeneity_score,
    normalized_mutual_info_score,
    v_measure_score,
)


VERSION = "comparison-evaluator-v2"
STAGE_3_6_PREFIXES = (
    "canonicalize_stage3",
    "stage3",
    "stage_3",
    "stage4",
    "stage_4",
    "stage5",
    "stage_5",
    "stage6",
    "stage_6",
)


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _norm(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.casefold().split())


def _rows06(path: Path) -> list[dict]:
    data = _load(path)
    if isinstance(data, list):
        return data
    for key in ("classificados", "classificacoes", "rows"):
        if isinstance(data.get(key), list):
            return data[key]
    raise RuntimeError(f"formato de Stage 6 nao reconhecido: {path}")


def _run_map(config: dict, base: Path) -> dict[str, dict]:
    output = {}
    native = config.get("native_m1")
    if native:
        row = dict(native)
        row["_path"] = (base / row["pipeline_data"]).resolve()
        output[row["id"]] = row
    for source in config.get("runs", []):
        row = dict(source)
        row["_path"] = (base / row["pipeline_data"]).resolve()
        output[row["id"]] = row
    return output


def _reference_views(reference_path: Path) -> tuple[dict, dict[str, dict]]:
    data = _load(reference_path)
    rows = data.get("classificacoes")
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("referencia sem classificacoes")
    views = {
        "consensus_full": {},
        "consensus_strict": {},
        "model_a": {},
        "model_b": {},
    }
    metadata = {}
    for row in rows:
        key = str(row.get("chave", "")).strip()
        if not key or key in metadata:
            raise RuntimeError("referencia com chave vazia ou duplicada")
        metadata[key] = row
        views["consensus_full"][key] = row.get("categoria_cobertura_id")
        views["consensus_strict"][key] = row.get("categoria_estrita_id")
        views["model_a"][key] = row.get("modelo_a_id")
        views["model_b"][key] = row.get("modelo_b_id")
    return data.get("metadata") or {}, views


def _target_metadata(portfolio_path: Path) -> tuple[dict, set[str], dict[str, str]]:
    data = _load(portfolio_path)
    categories = data.get("categorias_analiticas") or []
    by_id = {str(item["id"]): item for item in categories}
    service_ids = {
        category_id for category_id, item in by_id.items()
        if item.get("entra_macro_f1_servicos", True)
        and item.get("papel_analise") != "catch_all"
    }
    group_by_id = {
        category_id: str(item.get("grupo_id", ""))
        for category_id, item in by_id.items()
    }
    return by_id, service_ids, group_by_id


def _stage3_partition(path: Path) -> dict[str, str | None]:
    data = _load(path)
    output = {}
    for row in data.get("tickets") or []:
        key = str(row.get("chave", "")).strip()
        cluster = row.get("cluster_id")
        if cluster is not None and int(cluster) >= 0:
            label = f"cluster:{int(cluster)}"
        else:
            outlier = str(row.get("outlier_id") or "residual")
            label = f"outlier:{outlier}"
        if not key or key in output:
            raise RuntimeError(f"Stage 3 com chave vazia/duplicada: {path}")
        output[key] = label
    return output


def _stage6_partitions(path: Path) -> tuple[dict[str, str | None], dict[str, str | None], dict]:
    leaf = {}
    groups = {}
    rows = _rows06(path)
    pending = 0
    ambiguity = 0
    low_confidence = 0
    for row in rows:
        key = str(row.get("chave", "")).strip()
        if not key or key in leaf:
            raise RuntimeError(f"Stage 6 com chave vazia/duplicada: {path}")
        leaf_label = row.get("categoria_id") or row.get("categoria_nova")
        group_label = row.get("grupo_novo") or leaf_label
        leaf[key] = str(leaf_label).strip() if leaf_label else None
        groups[key] = str(group_label).strip() if group_label else None
        if not leaf[key] or row.get("_pendente"):
            pending += 1
        ambiguity += int(bool(row.get("ambiguidade")))
        low_confidence += int(str(row.get("confianca", "")).lower() == "baixa")
    return leaf, groups, {
        "n": len(rows),
        "pendentes": pending,
        "ambiguos": ambiguity,
        "baixa_confianca": low_confidence,
        "n_leaf": len({value for value in leaf.values() if value is not None}),
        "n_groups": len({value for value in groups.values() if value is not None}),
    }


def _contingency(
    predicted: list[str],
    reference: list[str],
) -> tuple[list[str], list[str], np.ndarray]:
    pred_labels = sorted(set(predicted), key=str)
    ref_labels = sorted(set(reference), key=str)
    pred_index = {label: index for index, label in enumerate(pred_labels)}
    ref_index = {label: index for index, label in enumerate(ref_labels)}
    matrix = np.zeros((len(pred_labels), len(ref_labels)), dtype=np.int64)
    for pred, ref in zip(predicted, reference):
        matrix[pred_index[pred], ref_index[ref]] += 1
    return pred_labels, ref_labels, matrix


def _bcubed(matrix: np.ndarray) -> tuple[float, float, float]:
    total = int(matrix.sum())
    if not total:
        return 0.0, 0.0, 0.0
    row_sums = matrix.sum(axis=1)
    col_sums = matrix.sum(axis=0)
    precision = sum(
        float(value * value) / float(row_sums[i])
        for i in range(matrix.shape[0])
        for value in matrix[i, :]
        if value and row_sums[i]
    ) / total
    recall = sum(
        float(value * value) / float(col_sums[j])
        for j in range(matrix.shape[1])
        for value in matrix[:, j]
        if value and col_sums[j]
    ) / total
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )
    return precision, recall, f1


def _material_structure(
    pred_labels: list[str],
    ref_labels: list[str],
    matrix: np.ndarray,
    rule: dict,
) -> dict:
    minimum_n = int(rule.get("minimum_n", 5))
    minimum_row = float(rule.get("minimum_row_share", 0.1))
    minimum_col = float(rule.get("minimum_column_share", 0.1))
    row_sums = matrix.sum(axis=1)
    col_sums = matrix.sum(axis=0)
    material = np.zeros_like(matrix, dtype=bool)
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            n = int(matrix[i, j])
            if n < minimum_n:
                continue
            row_share = n / max(int(row_sums[i]), 1)
            col_share = n / max(int(col_sums[j]), 1)
            material[i, j] = row_share >= minimum_row or col_share >= minimum_col
    reference_fragmentation = {
        ref_labels[j]: int(material[:, j].sum()) - 1
        for j in range(len(ref_labels))
        if int(material[:, j].sum()) > 1
    }
    predicted_conflation = {
        pred_labels[i]: int(material[i, :].sum()) - 1
        for i in range(len(pred_labels))
        if int(material[i, :].sum()) > 1
    }
    no_match = [
        ref_labels[j] for j in range(len(ref_labels))
        if int(material[:, j].sum()) == 0
    ]
    removable = [
        pred_labels[i] for i in range(len(pred_labels))
        if int(material[i, :].sum()) == 0
    ]
    return {
        "rule": {
            "minimum_n": minimum_n,
            "minimum_row_share": minimum_row,
            "minimum_column_share": minimum_col,
            "share_logic": "row_or_column",
        },
        # Um servico de referencia fragmentado em varias categorias preditas
        # exige fusoes para chegar ao alvo. Uma categoria predita que mistura
        # varios servicos exige divisoes.
        "merge_operations_to_target_lower_bound": sum(
            reference_fragmentation.values()
        ),
        "split_operations_to_target_lower_bound": sum(
            predicted_conflation.values()
        ),
        "reference_fragmentation_by_prediction": reference_fragmentation,
        "predicted_conflation_of_reference": predicted_conflation,
        "services_without_material_match": no_match,
        "predicted_categories_without_material_match": removable,
    }


def _partition_metrics(
    predicted_by_key: dict[str, str | None],
    reference_by_key: dict[str, str | None],
    service_ids: set[str],
    target_by_id: dict,
    material_rule: dict,
    key_subset: list[str] | None = None,
) -> dict:
    keys = key_subset or sorted(set(predicted_by_key) & set(reference_by_key))
    keys = [
        key for key in keys
        if predicted_by_key.get(key) is not None
        and reference_by_key.get(key) is not None
    ]
    if len(keys) < 2:
        return {"n": len(keys), "error": "insufficient_rows"}
    predicted = [str(predicted_by_key[key]) for key in keys]
    reference = [str(reference_by_key[key]) for key in keys]
    pred_labels, ref_labels, matrix = _contingency(predicted, reference)
    row_sums = matrix.sum(axis=1)
    col_sums = matrix.sum(axis=0)
    bc_p, bc_r, bc_f1 = _bcubed(matrix)

    per_reference = {}
    for j, ref in enumerate(ref_labels):
        best_f1 = 0.0
        best_pred = None
        best_overlap = 0
        for i, pred in enumerate(pred_labels):
            overlap = int(matrix[i, j])
            denom = int(row_sums[i] + col_sums[j])
            f1 = 2 * overlap / denom if denom else 0.0
            if f1 > best_f1:
                best_f1 = f1
                best_pred = pred
                best_overlap = overlap
        per_reference[ref] = {
            "nome": target_by_id.get(ref, {}).get("nome", ref),
            "support": int(col_sums[j]),
            "best_predicted_label": best_pred,
            "best_overlap": best_overlap,
            "best_match_f1": round(best_f1, 6),
        }
    macro_values = [
        per_reference[ref]["best_match_f1"]
        for ref in sorted(service_ids)
        if ref in per_reference
    ]
    missing_macro_services = sorted(
        service_ids - set(per_reference)
    )
    macro = (
        sum(macro_values) / len(service_ids)
        if service_ids
        else 0.0
    )

    minimum_reassignments = int(
        len(keys) - sum(int(row.max()) for row in matrix)
    )
    row_ind, col_ind = linear_sum_assignment(-matrix)
    hungarian_correct = int(matrix[row_ind, col_ind].sum())
    hungarian_per_ref = {ref: 0.0 for ref in ref_labels}
    for i, j in zip(row_ind, col_ind):
        overlap = int(matrix[i, j])
        denom = int(row_sums[i] + col_sums[j])
        hungarian_per_ref[ref_labels[j]] = 2 * overlap / denom if denom else 0.0

    contingency = {
        pred_labels[i]: {
            ref_labels[j]: int(matrix[i, j])
            for j in range(len(ref_labels))
            if int(matrix[i, j])
        }
        for i in range(len(pred_labels))
    }
    return {
        "n": len(keys),
        "n_predicted": len(pred_labels),
        "n_reference": len(ref_labels),
        "adjusted_rand_index": round(
            float(adjusted_rand_score(reference, predicted)), 6
        ),
        "adjusted_mutual_information": round(
            float(adjusted_mutual_info_score(reference, predicted)), 6
        ),
        "normalized_mutual_information": round(
            float(normalized_mutual_info_score(reference, predicted)), 6
        ),
        "homogeneity": round(float(homogeneity_score(reference, predicted)), 6),
        "completeness": round(float(completeness_score(reference, predicted)), 6),
        "v_measure": round(float(v_measure_score(reference, predicted)), 6),
        "fowlkes_mallows": round(
            float(fowlkes_mallows_score(reference, predicted)), 6
        ),
        "bcubed_precision": round(bc_p, 6),
        "bcubed_recall": round(bc_r, 6),
        "bcubed_f1": round(bc_f1, 6),
        "macro_best_match_f1_services": round(macro, 6),
        "macro_services_denominator": len(service_ids),
        "missing_macro_services": missing_macro_services,
        "per_reference": per_reference,
        "minimum_reassignments_after_free_rename": minimum_reassignments,
        "minimum_reassignment_rate": round(
            minimum_reassignments / len(keys), 6
        ),
        "hungarian_one_to_one_accuracy": round(
            hungarian_correct / len(keys), 6
        ),
        "hungarian_macro_f1_all_reference": round(
            sum(hungarian_per_ref.values()) / max(len(ref_labels), 1),
            6,
        ),
        "structure": _material_structure(
            pred_labels,
            ref_labels,
            matrix,
            material_rule,
        ),
        "contingency": contingency,
    }


def _metrics_time(path: Path) -> dict:
    if not path.exists():
        return {
            "latest_successful": {},
            "successful_total": {},
            "attempted": {},
            "failed": {},
        }
    latest_successful = {}
    successful_total = {}
    attempted = {}
    failed = {}
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    for line in lines[1:]:
        parts = [part.strip() for part in line.split(",")]
        if len(parts) >= 4:
            try:
                seconds = int(float(parts[3]))
                status = int(parts[4]) if len(parts) >= 5 and parts[4] else 0
            except ValueError:
                continue
            key = parts[0]
            attempted[key] = attempted.get(key, 0) + seconds
            if status == 0:
                latest_successful[key] = seconds
                successful_total[key] = successful_total.get(key, 0) + seconds
            else:
                failed[key] = failed.get(key, 0) + seconds
    return {
        "latest_successful": latest_successful,
        "successful_total": successful_total,
        "attempted": attempted,
        "failed": failed,
    }


def _metrics_tokens(path: Path) -> dict:
    output = {
        "available": False,
        "file_exists": path.exists(),
        "calls": 0,
        "calls_with_token_counts": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "by_stage": {},
        "by_model": {},
    }
    if not path.exists():
        return output
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        output["calls"] += 1
        raw_prompt = row.get("prompt_eval_count")
        raw_completion = row.get("eval_count")
        raw_total = row.get("total_tokens")
        has_token_count = any(
            isinstance(value, (int, float))
            for value in (raw_prompt, raw_completion, raw_total)
        )
        prompt = int(raw_prompt or 0)
        completion = int(raw_completion or 0)
        total = int(raw_total or (prompt + completion))
        if has_token_count:
            output["calls_with_token_counts"] += 1
        output["prompt_tokens"] += prompt
        output["completion_tokens"] += completion
        output["total_tokens"] += total
        for dimension, field in (("by_stage", "stage"), ("by_model", "model")):
            key = str(row.get(field) or "?")
            bucket = output[dimension].setdefault(
                key,
                {
                    "calls": 0,
                    "calls_with_token_counts": 0,
                    "tokens": 0,
                },
            )
            bucket["calls"] += 1
            if has_token_count:
                bucket["calls_with_token_counts"] += 1
            bucket["tokens"] += total
    output["available"] = output["calls_with_token_counts"] > 0
    expected_stages = {f"stage{stage}" for stage in range(3, 7)}
    observed_stages = {
        stage.casefold().replace("_", "")
        for stage, item in output["by_stage"].items()
        if item["calls_with_token_counts"] > 0
    }
    output["token_count_stage_coverage"] = {
        stage: any(
            observed.startswith(stage) for observed in observed_stages
        )
        for stage in sorted(expected_stages)
    }
    return output


def _stage_windows(path: Path) -> list[tuple[float, float]]:
    if not path.exists():
        return []
    windows = []
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        for row in csv.DictReader(handle):
            label = str(row.get("stage") or "").casefold()
            if not label.startswith(STAGE_3_6_PREFIXES):
                continue
            try:
                started = float(row.get("inicio_epoch") or "")
                finished = float(row.get("fim_epoch") or "")
            except (TypeError, ValueError):
                continue
            if finished >= started:
                windows.append((started, finished))
    return windows


def _gpu_epoch(value: str) -> float | None:
    value = str(value or "").strip()
    try:
        return float(value)
    except ValueError:
        pass
    for pattern in ("%Y/%m/%d %H:%M:%S.%f", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(value, pattern).astimezone().timestamp()
        except ValueError:
            continue
    return None


def _metrics_gpu(path: Path, time_path: Path) -> dict:
    output = {
        "available": False,
        "sample_count": 0,
        "sampled_seconds": 0.0,
        "utilization_mean_pct": None,
        "utilization_p95_pct": None,
        "memory_peak_mib": None,
        "memory_total_mib": None,
        "power_mean_w": None,
        "power_p95_w": None,
        "energy_estimated_wh": None,
        "scope": "attempted_stage_3_6_windows",
    }
    windows = _stage_windows(time_path)
    if not path.exists() or not windows:
        return output
    samples = []
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        for row in csv.DictReader(handle):
            epoch = _gpu_epoch(row.get("epoch") or row.get("timestamp") or "")
            if epoch is None or not any(start <= epoch <= end for start, end in windows):
                continue
            try:
                samples.append({
                    "epoch": epoch,
                    "util": float(row.get("gpu_util_pct") or ""),
                    "used": float(row.get("mem_used_mib") or ""),
                    "total": float(row.get("mem_total_mib") or ""),
                    "power": float(row.get("power_w") or ""),
                })
            except (TypeError, ValueError):
                continue
    if not samples:
        return output
    samples.sort(key=lambda row: row["epoch"])
    util = [row["util"] for row in samples]
    used = [row["used"] for row in samples]
    total = [row["total"] for row in samples]
    power = [row["power"] for row in samples]
    energy_ws = 0.0
    sampled_seconds = 0.0
    for start, finish in windows:
        in_window = [
            row for row in samples if start <= row["epoch"] <= finish
        ]
        for left, right in zip(in_window, in_window[1:]):
            delta = right["epoch"] - left["epoch"]
            if delta <= 0:
                continue
            sampled_seconds += delta
            energy_ws += delta * (left["power"] + right["power"]) / 2.0
    return {
        "available": True,
        "sample_count": len(samples),
        "sampled_seconds": round(sampled_seconds, 3),
        "utilization_mean_pct": round(float(statistics.fmean(util)), 3),
        "utilization_p95_pct": round(float(np.quantile(util, 0.95)), 3),
        "memory_peak_mib": round(max(used), 3),
        "memory_total_mib": round(max(total), 3),
        "power_mean_w": round(float(statistics.fmean(power)), 3),
        "power_p95_w": round(float(np.quantile(power, 0.95)), 3),
        "energy_estimated_wh": round(energy_ws / 3600.0, 3),
        "scope": "attempted_stage_3_6_windows",
    }


def _cost(path: Path) -> dict:
    time_path = path / "_metrics_tempo.csv"
    time_metrics = _metrics_time(time_path)
    time_rows = time_metrics["latest_successful"]
    stage_seconds = {
        key: value for key, value in time_rows.items()
        if key.casefold().startswith(STAGE_3_6_PREFIXES)
    }
    attempted_stage_seconds = {
        key: value for key, value in time_metrics["attempted"].items()
        if key.casefold().startswith(STAGE_3_6_PREFIXES)
    }
    normalized_stage_labels = {
        key.casefold().replace("_", "")
        for key in stage_seconds
        if not key.casefold().startswith("canonicalize")
    }
    required_stage_coverage = {
        f"stage{stage}": any(
            label.startswith(f"stage{stage}")
            for label in normalized_stage_labels
        )
        for stage in range(3, 7)
    }
    tags_path = path / "_environment_ollama_tags.json"
    models = []
    if tags_path.exists():
        try:
            models = [
                {
                    "name": row.get("name"),
                    "digest": row.get("digest"),
                    "size": row.get("size"),
                }
                for row in (_load(tags_path).get("models") or [])
            ]
        except Exception:
            models = []
    return {
        "wall_seconds_by_stage": time_rows,
        "wall_seconds_stages_3_6_available": all(
            required_stage_coverage.values()
        ),
        "required_stage_coverage": required_stage_coverage,
        "wall_seconds_stages_3_6": sum(stage_seconds.values()),
        "successful_attempt_seconds_by_stage_total": time_metrics[
            "successful_total"
        ],
        "wall_seconds_attempted_stages_3_6": sum(
            attempted_stage_seconds.values()
        ),
        "failed_attempt_seconds_by_stage": time_metrics["failed"],
        "tokens": _metrics_tokens(path / "_metrics_tokens.jsonl"),
        "gpu": _metrics_gpu(path / "_metrics_gpu.csv", time_path),
        "ollama_models": models,
        "environment_files": {
            name: _hash_file(path / name)
            for name in (
                "_environment_ollama_tags.json",
                "_environment_ollama_version.json",
                "_environment_nvidia.txt",
                "_environment_gpu_name.txt",
                "_environment_gpu_identity.txt",
                "_environment_lscpu.txt",
                "_environment_python.txt",
                "_environment_pip_freeze.txt",
                "_environment_numpy_config.txt",
                "_environment_code_sha256.txt",
                "_environment_verification.json",
            )
            if (path / name).exists()
        },
    }


def _bootstrap_primary_difference(
    predicted_a: dict[str, str | None],
    predicted_b: dict[str, str | None],
    reference: dict[str, str | None],
    service_ids: set[str],
    target_by_id: dict,
    material_rule: dict,
    replicates: int,
    seed: int,
    confidence: float,
) -> dict:
    keys = sorted(set(predicted_a) & set(predicted_b) & set(reference))
    keys = [
        key for key in keys
        if predicted_a.get(key) is not None
        and predicted_b.get(key) is not None
        and reference.get(key) is not None
    ]
    if not keys or replicates <= 0:
        return {"n": len(keys), "replicates": 0}
    rng = np.random.default_rng(seed)
    differences = np.empty(replicates, dtype=np.float64)
    n = len(keys)
    for index in range(replicates):
        sample_idx = rng.integers(0, n, size=n)
        sample_keys = [keys[int(i)] for i in sample_idx]
        # Chaves repetidas sao preservadas como observacoes usando labels diretos.
        pred_a = [str(predicted_a[key]) for key in sample_keys]
        pred_b = [str(predicted_b[key]) for key in sample_keys]
        ref = [str(reference[key]) for key in sample_keys]

        def macro(predicted: list[str]) -> float:
            _, ref_labels, matrix = _contingency(predicted, ref)
            row_sums = matrix.sum(axis=1)
            col_sums = matrix.sum(axis=0)
            values = {}
            for j, ref_label in enumerate(ref_labels):
                values[ref_label] = max(
                    (
                        2 * int(matrix[i, j])
                        / max(int(row_sums[i] + col_sums[j]), 1)
                        for i in range(matrix.shape[0])
                    ),
                    default=0.0,
                )
            return sum(values.get(service, 0.0) for service in service_ids) / max(
                len(service_ids), 1
            )

        differences[index] = macro(pred_b) - macro(pred_a)
    alpha = (1.0 - confidence) / 2.0
    return {
        "n": n,
        "replicates": replicates,
        "seed": seed,
        "confidence": confidence,
        "difference_definition": "method_b_minus_method_a",
        "mean": round(float(differences.mean()), 6),
        "median": round(float(np.median(differences)), 6),
        "ci_low": round(float(np.quantile(differences, alpha)), 6),
        "ci_high": round(float(np.quantile(differences, 1 - alpha)), 6),
        "probability_b_gt_a": round(float(np.mean(differences > 0)), 6),
    }


def _direction(diff: float, margin: float) -> str:
    if diff > margin:
        return "llm"
    if diff < -margin:
        return "kmeans"
    return "equivalent"


def _pair_direction(
    diff_right_minus_left: float,
    margin: float,
    left_name: str,
    right_name: str,
) -> str:
    if diff_right_minus_left > margin:
        return right_name
    if diff_right_minus_left < -margin:
        return left_name
    return "equivalent"


def _grid_sensitivity(cube: dict) -> dict:
    """Decompoe mudancas de direcao por seed, referencia e camada."""
    cells = []
    for seed, views in cube.items():
        for view, layers in views.items():
            for layer, item in layers.items():
                direction = item.get("direction")
                if direction:
                    cells.append({
                        "seed": str(seed),
                        "view": str(view),
                        "layer": str(layer),
                        "direction": str(direction),
                        "difference": item.get(
                            "difference_llm_minus_kmeans",
                            item.get("difference_m2_minus_m1"),
                        ),
                    })

    def variations(group_fields: tuple[str, ...], varying_field: str) -> list:
        grouped = defaultdict(list)
        for cell in cells:
            grouped[tuple(cell[field] for field in group_fields)].append(cell)
        output = []
        for group, group_cells in sorted(grouped.items()):
            directions = sorted({
                cell["direction"] for cell in group_cells
            })
            varying_values = sorted({
                cell[varying_field] for cell in group_cells
            })
            if len(directions) > 1 and len(varying_values) > 1:
                output.append({
                    "fixed": dict(zip(group_fields, group)),
                    f"{varying_field}_values": varying_values,
                    "directions": directions,
                })
        return output

    seed_variations = variations(("view", "layer"), "seed")
    reference_variations = variations(("seed", "layer"), "view")
    layer_variations = variations(("seed", "view"), "layer")
    return {
        "seed_sensitive": bool(seed_variations),
        "reference_sensitive": bool(reference_variations),
        "layer_sensitive": bool(layer_variations),
        "seed_variations": seed_variations,
        "reference_variations": reference_variations,
        "layer_variations": layer_variations,
        "cells": cells,
    }


def _secondary_dominance(
    left: dict,
    right: dict,
    rules: dict,
    left_name: str,
    right_name: str,
) -> dict:
    config = rules.get("secondary_dominance") or {}
    specs = config.get("metrics") or {}
    comparisons = OrderedDict()
    wins = {left_name: 0, right_name: 0}
    for metric in rules.get("secondary_metrics") or []:
        spec = specs.get(metric) or {}
        if metric not in left or metric not in right:
            continue
        raw_difference = float(right[metric]) - float(left[metric])
        favorable_to_right = (
            -raw_difference
            if spec.get("better") == "lower"
            else raw_difference
        )
        margin = float(spec.get("margin", 0.0))
        direction = _pair_direction(
            favorable_to_right,
            margin,
            left_name,
            right_name,
        )
        if direction in wins:
            wins[direction] += 1
        comparisons[metric] = {
            "left": float(left[metric]),
            "right": float(right[metric]),
            "raw_difference_right_minus_left": round(raw_difference, 6),
            "favorable_difference_for_right": round(favorable_to_right, 6),
            "better": spec.get("better", "higher"),
            "margin": margin,
            "direction": direction,
        }
    minimum = int(config.get("minimum_material_wins", 2))
    require_zero = bool(config.get("require_zero_material_losses", True))
    winner = None
    for candidate, opponent in (
        (left_name, right_name),
        (right_name, left_name),
    ):
        if wins[candidate] >= minimum and (
            not require_zero or wins[opponent] == 0
        ):
            winner = candidate if winner is None else None
    return {
        "winner": winner,
        "material_wins": wins,
        "minimum_material_wins": minimum,
        "require_zero_material_losses": require_zero,
        "metrics": comparisons,
    }


def _secondary_conflicts(primary_direction: str, secondary: dict) -> bool:
    winner = secondary.get("winner")
    if not winner:
        return False
    return (
        primary_direction == "equivalent"
        or winner != primary_direction
    )


def _strategic_protection(
    left: dict,
    right: dict,
    winner: str | None,
    left_name: str,
    right_name: str,
    rules: dict,
) -> dict:
    details = {}
    passed = True
    threshold = float(rules.get("maximum_strategic_service_loss", 0.1))
    minimum_support = int(
        rules.get("minimum_strategic_service_support", 5)
    )
    unevaluable_services = []
    for service in rules.get("strategic_service_ids", []):
        left_item = left.get("per_reference", {}).get(service) or {}
        right_item = right.get("per_reference", {}).get(service) or {}
        left_support = int(left_item.get("support") or 0)
        right_support = int(right_item.get("support") or 0)
        evaluable = (
            left_support >= minimum_support
            and right_support >= minimum_support
        )
        left_f1 = float(left_item.get("best_match_f1") or 0.0)
        right_f1 = float(right_item.get("best_match_f1") or 0.0)
        winner_minus_other = (
            right_f1 - left_f1 if winner == right_name
            else left_f1 - right_f1 if winner == left_name
            else 0.0
        )
        details[service] = {
            f"{left_name}_f1": left_f1,
            f"{right_name}_f1": right_f1,
            f"{left_name}_support": left_support,
            f"{right_name}_support": right_support,
            "minimum_support": minimum_support,
            "evaluable": evaluable,
            "winner_minus_other": round(winner_minus_other, 6),
        }
        if not evaluable:
            passed = False
            unevaluable_services.append(service)
        elif winner and winner_minus_other < -threshold:
            passed = False
    return {
        "threshold": threshold,
        "minimum_support": minimum_support,
        "passed": passed,
        "unevaluable_services": unevaluable_services,
        "details": details,
    }


def _cost_comparison(
    results: dict,
    left_ids: list[str],
    right_ids: list[str],
    left_name: str,
    right_name: str,
    rules: dict,
) -> dict:
    values_by_run = {
        run_id: results[run_id]["cost"]["wall_seconds_stages_3_6"]
        for run_id in left_ids + right_ids
        if run_id in results
        and results[run_id]["cost"].get(
            "wall_seconds_stages_3_6_available"
        )
    }
    left_values = [
        values_by_run[run_id]
        for run_id in left_ids
        if run_id in values_by_run
    ]
    right_values = [
        values_by_run[run_id]
        for run_id in right_ids
        if run_id in values_by_run
    ]
    available = bool(left_values) and bool(right_values)
    left_value = (
        float(statistics.median(left_values)) if left_values else None
    )
    right_value = (
        float(statistics.median(right_values)) if right_values else None
    )
    minimum_relative = float(
        (rules.get("cost_tiebreaker") or {}).get(
            "minimum_relative_difference",
            0.1,
        )
    )
    winner = None
    relative_difference = None
    if available:
        denominator = max(left_value, right_value, 1.0)
        relative_difference = abs(right_value - left_value) / denominator
        if relative_difference < minimum_relative:
            winner = "equivalent"
        elif left_value < right_value:
            winner = left_name
        else:
            winner = right_name
    return {
        "metric": "wall_seconds_stages_3_6",
        "available_for_both": available,
        "aggregation": "median",
        "run_ids": {left_name: left_ids, right_name: right_ids},
        "values_by_run": values_by_run,
        "aggregated_values": {
            left_name: left_value,
            right_name: right_value,
        },
        "minimum_relative_difference": minimum_relative,
        "observed_relative_difference": (
            round(relative_difference, 6)
            if relative_difference is not None else None
        ),
        "winner": winner,
        "tokens_and_gpu_not_composited": True,
    }


def _conclusion(
    *,
    results: dict,
    partitions: dict,
    run_configs: dict,
    config: dict,
    rules: dict,
    reference_views: dict,
    service_ids: set[str],
    target_by_id: dict,
    material_rule: dict,
) -> dict:
    primary_ids = config["comparisons"]["fair_ablation_primary"]
    kmeans_id = next(
        run_id for run_id in primary_ids
        if run_configs[run_id].get("discovery") == "kmeans"
    )
    llm_id = next(
        run_id for run_id in primary_ids
        if run_configs[run_id].get("discovery") == "llm"
    )
    margin = float(rules["practical_equivalence_margin"])
    view_differences = {}
    view_directions = {}
    expected_views = list(rules["reference_robustness"]["views"])
    primary_view = str(
        rules["reference_robustness"].get(
            "primary_view",
            "consensus_full",
        )
    )
    if primary_view not in expected_views:
        raise RuntimeError("primary reference view nao esta na grade")
    minimum_coverage = (
        rules["reference_robustness"].get("minimum_coverage") or {}
    )
    view_coverage = {}
    full_n = max(len(reference_views.get(primary_view) or {}), 1)
    for view in expected_views:
        left = results[kmeans_id]["views"][view]["final_request_types"]
        right = results[llm_id]["views"][view]["final_request_types"]
        if "error" in left or "error" in right:
            view_coverage[view] = 0.0
            continue
        view_coverage[view] = min(
            int(left.get("n", 0)),
            int(right.get("n", 0)),
        ) / full_n
        diff = (
            right["macro_best_match_f1_services"]
            - left["macro_best_match_f1_services"]
        )
        view_differences[view] = round(diff, 6)
        view_directions[view] = _direction(diff, margin)

    bootstrap_cfg = rules.get("bootstrap") or {}
    bootstrap_by_reference_view = OrderedDict()
    for index, view in enumerate(expected_views):
        bootstrap_by_reference_view[view] = _bootstrap_primary_difference(
            partitions[kmeans_id]["final_request_types"],
            partitions[llm_id]["final_request_types"],
            reference_views[view],
            service_ids,
            target_by_id,
            material_rule,
            int(bootstrap_cfg.get("replicates", 2000)),
            int(bootstrap_cfg.get("seed", 20260723)) + index,
            float(bootstrap_cfg.get("confidence", 0.95)),
        )
    bootstrap = bootstrap_by_reference_view[primary_view]
    main_direction = view_directions.get(primary_view, "equivalent")
    reference_complete = all(
        view in view_directions
        and view_coverage.get(view, 0.0)
        >= float(minimum_coverage.get(view, 1.0))
        for view in expected_views
    )
    reference_sensitive = not reference_complete
    layer_differences = OrderedDict()
    layer_directions = OrderedDict()
    for layer in ("discovery", "final_request_types", "final_groups"):
        left_layer = results[kmeans_id]["views"][primary_view][layer]
        right_layer = results[llm_id]["views"][primary_view][layer]
        if "error" in left_layer or "error" in right_layer:
            continue
        difference = (
            right_layer["macro_best_match_f1_services"]
            - left_layer["macro_best_match_f1_services"]
        )
        layer_differences[layer] = round(difference, 6)
        layer_directions[layer] = _direction(difference, margin)
    layer_sensitive = False

    left = results[kmeans_id]["views"][primary_view]["final_request_types"]
    right = results[llm_id]["views"][primary_view]["final_request_types"]
    winner = main_direction if main_direction in {"llm", "kmeans"} else None
    strategic = _strategic_protection(
        left,
        right,
        winner,
        "kmeans",
        "llm",
        rules,
    )
    secondary = _secondary_dominance(
        left,
        right,
        rules,
        "kmeans",
        "llm",
    )
    secondary_conflict = _secondary_conflicts(main_direction, secondary)

    # Robustez entre sementes, quando as replicas existem.
    seed_directions = {}
    seed_reference_layer_cube = OrderedDict()
    by_discovery = config["comparisons"].get("fair_ablation_repeats") or {}
    k_runs = {
        int(run_configs[run_id].get("seed", 0)): run_id
        for run_id in by_discovery.get("kmeans", [])
        if run_id in results
    }
    l_runs = {
        int(run_configs[run_id].get("seed", 0)): run_id
        for run_id in by_discovery.get("llm", [])
        if run_id in results
    }
    for seed in sorted(set(k_runs) & set(l_runs)):
        seed_reference_layer_cube[str(seed)] = OrderedDict()
        for view in expected_views:
            seed_reference_layer_cube[str(seed)][view] = OrderedDict()
            for layer in ("discovery", "final_request_types", "final_groups"):
                k_metric = results[k_runs[seed]]["views"][view][layer]
                l_metric = results[l_runs[seed]]["views"][view][layer]
                if "error" in k_metric or "error" in l_metric:
                    continue
                diff = (
                    l_metric["macro_best_match_f1_services"]
                    - k_metric["macro_best_match_f1_services"]
                )
                item = {
                    "difference_llm_minus_kmeans": round(diff, 6),
                    "direction": _direction(diff, margin),
                }
                seed_reference_layer_cube[str(seed)][view][layer] = item
                if (
                    view == primary_view
                    and layer == "final_request_types"
                ):
                    seed_directions[str(seed)] = item
    grid_sensitivity = _grid_sensitivity(seed_reference_layer_cube)
    reference_sensitive = (
        reference_sensitive
        or grid_sensitivity["reference_sensitive"]
    )
    layer_sensitive = grid_sensitivity["layer_sensitive"]
    seed_sensitive = grid_sensitivity["seed_sensitive"]
    grid_complete = (
        len(seed_reference_layer_cube) >= 3
        and all(
            set(views) == set(expected_views)
            and all(
                set(layers)
                == {"discovery", "final_request_types", "final_groups"}
                for layers in views.values()
            )
            for views in seed_reference_layer_cube.values()
        )
    )
    repeats_complete = grid_complete
    discordant_cells = [
        cell for cell in grid_sensitivity["cells"]
        if cell["direction"] != main_direction
    ]

    strategic_grid_cells = OrderedDict()
    strategic_unevaluable_cells = []
    strategic_worst_loss = {
        service: None for service in rules.get("strategic_service_ids", [])
    }
    strategic_grid_passed = strategic["passed"]
    for seed, run_id_k in sorted(k_runs.items()):
        run_id_l = l_runs.get(seed)
        if not run_id_l:
            continue
        strategic_grid_cells[str(seed)] = OrderedDict()
        for view in expected_views:
            left_metric = results[run_id_k]["views"][view][
                "final_request_types"
            ]
            right_metric = results[run_id_l]["views"][view][
                "final_request_types"
            ]
            if "error" in left_metric or "error" in right_metric:
                continue
            guard = _strategic_protection(
                left_metric,
                right_metric,
                winner,
                "kmeans",
                "llm",
                rules,
            )
            strategic_grid_cells[str(seed)][view] = guard
            strategic_grid_passed = (
                strategic_grid_passed and guard["passed"]
            )
            for service in guard.get("unevaluable_services", []):
                strategic_unevaluable_cells.append({
                    "seed": str(seed),
                    "view": view,
                    "service": service,
                })
            for service, detail in guard["details"].items():
                if not detail.get("evaluable"):
                    continue
                observed = float(detail["winner_minus_other"])
                current = strategic_worst_loss.get(service)
                strategic_worst_loss[service] = (
                    observed if current is None else min(current, observed)
                )
    strategic_grid = {
        "scope": "all_available_seeds_x_reference_views_at_request_types",
        "passed": strategic_grid_passed,
        "evaluated_cells": sum(
            len(views) for views in strategic_grid_cells.values()
        ),
        "expected_cells_for_strong_claim": 12,
        "unevaluable_cells": strategic_unevaluable_cells,
        "worst_winner_minus_other_by_service": {
            service: (
                round(value, 6) if value is not None else None
            )
            for service, value in strategic_worst_loss.items()
        },
        "cells": strategic_grid_cells,
    }

    ci_excludes_zero_by_reference_view = {
        view: (
            item.get("replicates", 0) > 0
            and (
                item.get("ci_low", 0) > 0
                or item.get("ci_high", 0) < 0
            )
        )
        for view, item in bootstrap_by_reference_view.items()
    }
    ci_excludes_zero = (
        reference_complete
        and all(ci_excludes_zero_by_reference_view.values())
    )
    equivalence_ci_inside_margin_by_reference_view = {
        view: (
            item.get("replicates", 0) > 0
            and item.get("ci_low", -math.inf) >= -margin
            and item.get("ci_high", math.inf) <= margin
        )
        for view, item in bootstrap_by_reference_view.items()
    }
    equivalence_ci_inside_margin = (
        reference_complete
        and all(
            equivalence_ci_inside_margin_by_reference_view.values()
        )
    )
    margin_sensitivity = OrderedDict()
    sensitivity_margins = (
        list(rules.get("descriptive_margin_sensitivity") or [])
        + [margin]
    )
    for sensitivity_margin in sorted(set(
        float(value) for value in sensitivity_margins
    )):
        key = f"{sensitivity_margin:.2f}"
        directions = {
            view: _direction(diff, sensitivity_margin)
            for view, diff in view_differences.items()
        }
        margin_sensitivity[key] = {
            "decision_rule": sensitivity_margin == margin,
            "consensus_full_direction": directions.get("consensus_full"),
            "primary_view_direction": directions.get(primary_view),
            "all_reference_directions": directions,
            "all_references_same_direction": (
                len(set(directions.values())) <= 1
            ),
            "all_reference_bootstrap_cis_inside_equivalence_band": (
                all(
                    item.get("replicates", 0) > 0
                    and item.get("ci_low", -math.inf)
                    >= -sensitivity_margin
                    and item.get("ci_high", math.inf)
                    <= sensitivity_margin
                    for item in bootstrap_by_reference_view.values()
                )
            ),
        }
    cost_comparison = _cost_comparison(
        results,
        [
            run_id for run_id in by_discovery.get("kmeans", [])
            if run_id in results
        ],
        [
            run_id for run_id in by_discovery.get("llm", [])
            if run_id in results
        ],
        "kmeans",
        "llm",
        rules,
    )
    cost_winner = cost_comparison["winner"]

    if reference_sensitive:
        code = "inconclusivo_dependente_da_referencia"
    elif layer_sensitive:
        code = "inconclusivo_dependente_da_camada"
    elif seed_sensitive:
        code = "inconclusivo_dependente_da_semente"
    elif not strategic_grid["passed"] or secondary_conflict:
        code = "inconclusivo_metricas_conflitantes"
    elif main_direction == "equivalent":
        if not equivalence_ci_inside_margin:
            code = "inconclusivo_metricas_conflitantes"
        elif cost_winner == "kmeans":
            code = "equivalentes_kmeans_mais_eficiente"
        elif cost_winner == "llm":
            code = "equivalentes_llm_mais_eficiente"
        elif cost_winner == "equivalent":
            code = "equivalentes_sem_diferenca_material_de_custo"
        else:
            code = "equivalentes_custo_indisponivel"
    elif not ci_excludes_zero:
        code = "inconclusivo_metricas_conflitantes"
    elif (
        cost_winner in {"kmeans", "llm"}
        and cost_winner != main_direction
    ):
        code = "tradeoff_qualidade_custo"
    else:
        code = f"{main_direction}_superior_em_aderencia"

    if not repeats_complete:
        strength = "provisoria_sem_tres_replicas"
    elif (
        reference_sensitive
        or layer_sensitive
        or seed_sensitive
        or code.startswith("inconclusivo")
    ):
        strength = "inconclusiva_apos_testes_de_robustez"
    else:
        strength = "forte"
    return {
        "code": code,
        "strength": strength,
        "quality_winner": winner,
        "cost_winner": cost_winner,
        "primary_runs": {"kmeans": kmeans_id, "llm": llm_id},
        "practical_equivalence_margin": margin,
        "reference_view_differences": view_differences,
        "reference_view_directions": view_directions,
        "reference_view_coverage": view_coverage,
        "reference_views_complete": reference_complete,
        "reference_sensitive": reference_sensitive,
        "layer_differences_llm_minus_kmeans": layer_differences,
        "layer_directions": layer_directions,
        "layer_sensitive": layer_sensitive,
        "seed_sensitive": seed_sensitive,
        "robustness_dimension_details": {
            "reference": grid_sensitivity["reference_variations"],
            "layer": grid_sensitivity["layer_variations"],
            "seed": grid_sensitivity["seed_variations"],
        },
        "discordant_grid_cells_vs_primary": discordant_cells,
        "bootstrap": bootstrap,
        "primary_reference_view": primary_view,
        "bootstrap_by_reference_view": bootstrap_by_reference_view,
        "ci_excludes_zero_by_reference_view": (
            ci_excludes_zero_by_reference_view
        ),
        "ci_excludes_zero_all_reference_views": ci_excludes_zero,
        "equivalence_ci_inside_margin": equivalence_ci_inside_margin,
        "equivalence_ci_inside_margin_by_reference_view": (
            equivalence_ci_inside_margin_by_reference_view
        ),
        "margin_sensitivity_descriptive": margin_sensitivity,
        "secondary_dominance": secondary,
        "secondary_conflict": secondary_conflict,
        "strategic_service_protection": strategic,
        "strategic_service_protection_grid": strategic_grid,
        "seed_directions": seed_directions,
        "seed_reference_layer_cube": seed_reference_layer_cube,
        "seed_reference_layer_cube_complete": grid_complete,
        "three_replicates_complete": repeats_complete,
        "cost_comparison": cost_comparison,
        "cost_stages_3_6_seconds": {
            "kmeans": cost_comparison["aggregated_values"]["kmeans"],
            "llm": cost_comparison["aggregated_values"]["llm"],
        },
        "interpretation": (
            "A conclusao mede proximidade ao portfolio operacional curado ex post "
            "sob projecao automatica; nao prova verdade objetiva de rotulos."
        ),
    }


def _operational_comparison(
    *,
    results: dict,
    partitions: dict,
    config: dict,
    rules: dict,
    reference_views: dict,
    service_ids: set[str],
    target_by_id: dict,
    material_rule: dict,
) -> dict:
    run_ids = list(config["comparisons"].get("operational") or [])
    if len(run_ids) != 2:
        raise RuntimeError(
            "comparacao operacional deve declarar exatamente dois runs"
        )
    m1_id, m2_id = run_ids
    margin = float(rules["practical_equivalence_margin"])
    layer_differences = OrderedDict()
    layer_directions = OrderedDict()
    expected_views = list(rules["reference_robustness"]["views"])
    primary_view = str(
        rules["reference_robustness"].get(
            "primary_view",
            "consensus_full",
        )
    )
    if primary_view not in expected_views:
        raise RuntimeError("primary reference view nao esta na grade")
    minimum_coverage = (
        rules["reference_robustness"].get("minimum_coverage") or {}
    )
    view_coverage = {}
    full_n = max(len(reference_views.get(primary_view) or {}), 1)
    for view in expected_views:
        layer_differences[view] = OrderedDict()
        layer_directions[view] = OrderedDict()
        for layer in ("discovery", "final_request_types", "final_groups"):
            left = results[m1_id]["views"][view][layer]
            right = results[m2_id]["views"][view][layer]
            if "error" in left or "error" in right:
                continue
            diff = (
                right["macro_best_match_f1_services"]
                - left["macro_best_match_f1_services"]
            )
            layer_differences[view][layer] = round(diff, 6)
            layer_directions[view][layer] = _pair_direction(
                diff,
                margin,
                "m1",
                "m2",
            )
        primary_metric = results[m1_id]["views"][view]["final_request_types"]
        other_metric = results[m2_id]["views"][view]["final_request_types"]
        if "error" in primary_metric or "error" in other_metric:
            view_coverage[view] = 0.0
        else:
            view_coverage[view] = min(
                int(primary_metric.get("n", 0)),
                int(other_metric.get("n", 0)),
            ) / full_n

    primary_directions = {
        view: layers.get("final_request_types")
        for view, layers in layer_directions.items()
        if layers.get("final_request_types")
    }
    main_direction = primary_directions.get(primary_view, "equivalent")
    reference_complete = all(
        view in primary_directions
        and view_coverage.get(view, 0.0)
        >= float(minimum_coverage.get(view, 1.0))
        for view in expected_views
    )
    operational_cube = {
        "single_execution": {
            view: {
                layer: {
                    "difference_m2_minus_m1": (
                        layer_differences[view][layer]
                    ),
                    "direction": direction,
                }
                for layer, direction in layers.items()
            }
            for view, layers in layer_directions.items()
        }
    }
    grid_sensitivity = _grid_sensitivity(operational_cube)
    reference_sensitive = (
        not reference_complete
        or grid_sensitivity["reference_sensitive"]
    )
    layer_sensitive = grid_sensitivity["layer_sensitive"]

    left = results[m1_id]["views"][primary_view]["final_request_types"]
    right = results[m2_id]["views"][primary_view]["final_request_types"]
    winner = main_direction if main_direction in {"m1", "m2"} else None
    secondary = _secondary_dominance(
        left,
        right,
        rules,
        "m1",
        "m2",
    )
    secondary_conflict = _secondary_conflicts(main_direction, secondary)
    strategic = _strategic_protection(
        left,
        right,
        winner,
        "m1",
        "m2",
        rules,
    )
    strategic_grid_cells = OrderedDict()
    strategic_unevaluable_cells = []
    strategic_worst_loss = {
        service: None for service in rules.get("strategic_service_ids", [])
    }
    strategic_grid_passed = strategic["passed"]
    for view in expected_views:
        left_metric = results[m1_id]["views"][view][
            "final_request_types"
        ]
        right_metric = results[m2_id]["views"][view][
            "final_request_types"
        ]
        if "error" in left_metric or "error" in right_metric:
            continue
        guard = _strategic_protection(
            left_metric,
            right_metric,
            winner,
            "m1",
            "m2",
            rules,
        )
        strategic_grid_cells[view] = guard
        strategic_grid_passed = strategic_grid_passed and guard["passed"]
        for service in guard.get("unevaluable_services", []):
            strategic_unevaluable_cells.append({
                "view": view,
                "service": service,
            })
        for service, detail in guard["details"].items():
            if not detail.get("evaluable"):
                continue
            observed = float(detail["winner_minus_other"])
            current = strategic_worst_loss.get(service)
            strategic_worst_loss[service] = (
                observed if current is None else min(current, observed)
            )
    strategic_grid = {
        "scope": "four_reference_views_at_final_request_types_single_execution",
        "passed": strategic_grid_passed,
        "evaluated_cells": len(strategic_grid_cells),
        "expected_cells": 4,
        "unevaluable_cells": strategic_unevaluable_cells,
        "worst_winner_minus_other_by_service": {
            service: (
                round(value, 6) if value is not None else None
            )
            for service, value in strategic_worst_loss.items()
        },
        "cells": strategic_grid_cells,
    }
    bootstrap_cfg = rules.get("bootstrap") or {}
    bootstrap_by_reference_view = OrderedDict()
    for index, view in enumerate(expected_views):
        bootstrap_by_reference_view[view] = _bootstrap_primary_difference(
            partitions[m1_id]["final_request_types"],
            partitions[m2_id]["final_request_types"],
            reference_views[view],
            service_ids,
            target_by_id,
            material_rule,
            int(bootstrap_cfg.get("replicates", 2000)),
            int(bootstrap_cfg.get("seed", 20260723)) + 100 + index,
            float(bootstrap_cfg.get("confidence", 0.95)),
        )
    bootstrap = bootstrap_by_reference_view[primary_view]
    ci_excludes_zero_by_reference_view = {
        view: (
            item.get("replicates", 0) > 0
            and (
                item.get("ci_low", 0) > 0
                or item.get("ci_high", 0) < 0
            )
        )
        for view, item in bootstrap_by_reference_view.items()
    }
    ci_excludes_zero = (
        reference_complete
        and all(ci_excludes_zero_by_reference_view.values())
    )
    equivalence_ci_inside_margin_by_reference_view = {
        view: (
            item.get("replicates", 0) > 0
            and item.get("ci_low", -math.inf) >= -margin
            and item.get("ci_high", math.inf) <= margin
        )
        for view, item in bootstrap_by_reference_view.items()
    }
    equivalence_ci_inside_margin = (
        reference_complete
        and all(
            equivalence_ci_inside_margin_by_reference_view.values()
        )
    )
    cost_comparison = _cost_comparison(
        results,
        [m1_id],
        [m2_id],
        "m1",
        "m2",
        rules,
    )
    cost_winner = cost_comparison["winner"]

    if reference_sensitive:
        code = "operacional_inconclusivo_dependente_da_referencia"
    elif layer_sensitive:
        code = "operacional_inconclusivo_dependente_da_camada"
    elif not strategic_grid["passed"] or secondary_conflict:
        code = "operacional_inconclusivo_metricas_conflitantes"
    elif main_direction == "equivalent":
        if not equivalence_ci_inside_margin:
            code = "operacional_inconclusivo_metricas_conflitantes"
        elif cost_winner == "m1":
            code = "operacional_equivalentes_m1_mais_eficiente"
        elif cost_winner == "m2":
            code = "operacional_equivalentes_m2_mais_eficiente"
        elif cost_winner == "equivalent":
            code = (
                "operacional_equivalentes_sem_diferenca_material_de_custo"
            )
        else:
            code = "operacional_equivalentes_custo_indisponivel"
    elif not ci_excludes_zero:
        code = "operacional_inconclusivo_metricas_conflitantes"
    elif cost_winner in {"m1", "m2"} and cost_winner != main_direction:
        code = "operacional_tradeoff_qualidade_custo"
    else:
        code = f"operacional_{main_direction}_maior_aderencia_descritiva"

    return {
        "code": code,
        "strength": (
            "descritiva_inconclusiva"
            if "inconclusivo" in code
            else "descritiva_condicional_a_uma_execucao"
        ),
        "causal_interpretation": False,
        "claim_scope": (
            "benchmark das arquiteturas downstream nos Stages 3-6, "
            "condicionado ao mesmo Stage 2; o M1 e a arquitetura legada "
            "reexecutada do zero com Llama; uma unica "
            "execucao nao identifica causalmente qual componente explica "
            "a diferenca nem estima variancia entre execucoes"
        ),
        "runs": {"m1": m1_id, "m2": m2_id},
        "quality_winner": winner,
        "cost_winner": cost_winner,
        "practical_equivalence_margin": margin,
        "layer_differences_m2_minus_m1": layer_differences,
        "layer_directions": layer_directions,
        "reference_view_coverage": view_coverage,
        "reference_views_complete": reference_complete,
        "reference_sensitive": reference_sensitive,
        "layer_sensitive": layer_sensitive,
        "robustness_dimension_details": {
            "reference": grid_sensitivity["reference_variations"],
            "layer": grid_sensitivity["layer_variations"],
        },
        "bootstrap": bootstrap,
        "primary_reference_view": primary_view,
        "bootstrap_by_reference_view": bootstrap_by_reference_view,
        "ci_excludes_zero_by_reference_view": (
            ci_excludes_zero_by_reference_view
        ),
        "ci_excludes_zero_all_reference_views": ci_excludes_zero,
        "equivalence_ci_inside_margin": equivalence_ci_inside_margin,
        "equivalence_ci_inside_margin_by_reference_view": (
            equivalence_ci_inside_margin_by_reference_view
        ),
        "secondary_dominance": secondary,
        "secondary_conflict": secondary_conflict,
        "strategic_service_protection": strategic,
        "strategic_service_protection_grid": strategic_grid,
        "cost_comparison": cost_comparison,
    }


def _integrated_conclusion(
    operational: dict,
    fair: dict,
) -> dict:
    operational_problem = (
        "inconclusivo" in operational["code"]
        or operational.get("reference_sensitive")
        or operational.get("layer_sensitive")
    )
    fair_problem = (
        fair["code"].startswith("inconclusivo")
        or fair.get("strength") != "forte"
    )
    within_estimand_cost_tradeoff = (
        "tradeoff" in operational["code"]
        or "tradeoff" in fair["code"]
    )
    op_winner = operational.get("quality_winner")
    fair_winner = fair.get("quality_winner")
    adherence_convergent = (
        (op_winner == "m2" and fair_winner == "llm")
        or (op_winner == "m1" and fair_winner == "kmeans")
        or (op_winner is None and fair_winner is None)
    )
    operational_cost = operational.get("cost_winner")
    fair_cost = fair.get("cost_winner")
    cost_mapping = {
        "m1": "estatistico",
        "kmeans": "estatistico",
        "m2": "llm",
        "llm": "llm",
        "equivalent": "equivalent",
    }
    mapped_operational_cost = cost_mapping.get(operational_cost)
    mapped_fair_cost = cost_mapping.get(fair_cost)
    cost_evidence_available = (
        mapped_operational_cost is not None
        and mapped_fair_cost is not None
    )
    cost_evidence_convergent = (
        cost_evidence_available
        and mapped_operational_cost == mapped_fair_cost
    )
    if not cost_evidence_available:
        cost_synthesis_code = "custo_incompleto_entre_estimandos"
    elif cost_evidence_convergent:
        cost_synthesis_code = (
            f"custo_convergente_{mapped_operational_cost}"
        )
    else:
        cost_synthesis_code = "custos_divergentes_entre_estimandos"
    cost_tradeoff = (
        within_estimand_cost_tradeoff
        or (
            cost_evidence_available
            and not cost_evidence_convergent
        )
    )
    if operational_problem or fair_problem:
        code = "resultado_global_nao_unico"
    elif cost_tradeoff:
        code = "aderencia_convergente_com_tradeoff_de_custo" if (
            adherence_convergent
        ) else "resultado_global_nao_unico"
    else:
        if op_winner == "m2" and fair_winner == "llm":
            code = "evidencia_convergente_favoravel_ao_metodo_llm"
        elif op_winner == "m1" and fair_winner == "kmeans":
            code = "evidencia_convergente_favoravel_ao_metodo_estatistico"
        elif op_winner is None and fair_winner is None:
            code = "evidencia_convergente_de_equivalencia_pratica"
        else:
            code = "resultados_distintos_por_estimando"
    return {
        "code": code,
        "strength": (
            "condicional_a_uma_execucao_operacional"
            if not operational_problem and not fair_problem
            else "condicional_ou_provisoria"
        ),
        "adherence_strength": (
            "forte_na_ablacao_e_condicional_no_benchmark"
            if not operational_problem and not fair_problem
            else "nao_forte"
        ),
        "operational_code": operational["code"],
        "fair_ablation_code": fair["code"],
        "adherence_direction_convergent": adherence_convergent,
        "cost_tradeoff_present": cost_tradeoff,
        "within_estimand_cost_tradeoff": within_estimand_cost_tradeoff,
        "cost_synthesis_code": cost_synthesis_code,
        "cost_evidence_available": cost_evidence_available,
        "cost_evidence_convergent": cost_evidence_convergent,
        "cost_winners": {
            "operational": operational_cost,
            "fair_ablation": fair_cost,
        },
        "portfolio_decision": "portfolio_curado_permanece_adotado",
        "interpretation": (
            "O benchmark operacional e a ablacao respondem perguntas diferentes. "
            "A aderencia so e sintetizada quando as direcoes sao estaveis; o "
            "benchmark operacional continua condicionado a uma unica execucao. "
            "Custo e sintetizado separadamente e nunca e ocultado por uma "
            "conclusao de aderencia. O alvo curado nao vira verdade externa."
        ),
    }


def _pseudonymous_ledger(
    *,
    out_path: Path,
    secret_path: Path,
    keys: list[str],
    partitions: dict,
    reference_views: dict,
    reference_rows: dict,
) -> None:
    secret_path.parent.mkdir(parents=True, exist_ok=True)
    if secret_path.exists():
        secret = secret_path.read_bytes()
    else:
        secret = secrets.token_bytes(32)
        descriptor = os.open(
            secret_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        try:
            os.write(descriptor, secret)
        finally:
            os.close(descriptor)
    os.chmod(secret_path, 0o600)
    columns = ["eval_id"]
    for run_id in sorted(partitions):
        columns.extend([
            f"{run_id}__stage3",
            f"{run_id}__request_type",
            f"{run_id}__group",
        ])
    columns.extend([
        "reference__strict",
        "reference__full",
        "reference__model_a",
        "reference__model_b",
        "reference__status",
    ])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for key in keys:
            row = {
                "eval_id": hmac.new(
                    secret,
                    key.encode("utf-8"),
                    hashlib.sha256,
                ).hexdigest()[:20],
            }
            for run_id, layers in partitions.items():
                row[f"{run_id}__stage3"] = layers["discovery"].get(key)
                row[f"{run_id}__request_type"] = layers[
                    "final_request_types"
                ].get(key)
                row[f"{run_id}__group"] = layers["final_groups"].get(key)
            row["reference__strict"] = reference_views[
                "consensus_strict"
            ].get(key)
            row["reference__full"] = reference_views[
                "consensus_full"
            ].get(key)
            row["reference__model_a"] = reference_views["model_a"].get(key)
            row["reference__model_b"] = reference_views["model_b"].get(key)
            row["reference__status"] = reference_rows[key].get(
                "status_consenso"
            )
            writer.writerow(row)


def _render_markdown(report: dict, target_by_id: dict) -> str:
    integrated = report["integrated_conclusion"]
    operational = report["operational_comparison"]
    fair = report["fair_ablation_conclusion"]
    lines = [
        "# Resultado da comparação robusta de métodos",
        "",
        "> O alvo é o portfólio operacional curado ex post. A máscara de Sala "
        "de Sigilo é automática e conservadora: qualquer voto de Sala, "
        "ambiguidade ou baixa confiança põe o caso em quarentena antes dos "
        "métodos e métricas. Isso reduz risco de inclusão, mas não constitui "
        "prova externa de escopo.",
        "",
        "## Conclusão integrada",
        "",
        f"**{integrated['code']}** "
        f"(força: `{integrated['strength']}`).",
        "",
        integrated["interpretation"],
        "",
        f"Decisão operacional: **{integrated['portfolio_decision']}**.",
        "",
        f"Síntese de custo: **{integrated['cost_synthesis_code']}** "
        f"(disponível nos dois estimandos: "
        f"`{integrated['cost_evidence_available']}`; convergente: "
        f"`{integrated['cost_evidence_convergent']}`).",
        f"Vencedores de custo — benchmark: "
        f"`{integrated['cost_winners']['operational'] or 'n/d'}`; "
        f"ablação: `{integrated['cost_winners']['fair_ablation'] or 'n/d'}`.",
        "",
        "## Dois estimandos, duas conclusões",
        "",
        "### 1. Benchmark das arquiteturas downstream (Stages 3–6)",
        "",
        f"**{operational['code']}** "
        f"(força: `{operational['strength']}`).",
        "",
        operational["claim_scope"] + ".",
        "",
        "| Visão | Camada | Δ Macro-F1 (M2 − M1) | Direção |",
        "|---|---|---:|---|",
    ]
    for view, layers in operational[
        "layer_differences_m2_minus_m1"
    ].items():
        for layer, difference in layers.items():
            direction = operational["layer_directions"][view][layer]
            lines.append(
                f"| {view} | {layer} | {difference:+.3f} | {direction} |"
            )
    op_bootstrap = operational["bootstrap"]
    if op_bootstrap.get("replicates"):
        lines.extend([
            "",
            f"Visão primária: `{operational['primary_reference_view']}`. "
            "Cada visão recebe bootstrap próprio:",
            "",
            "| Visão | N | Δ médio | IC 95% | Exclui zero | "
            "IC inteiro em ±0,03 |",
            "|---|---:|---:|---|---|---|",
        ])
        for view, item in operational[
            "bootstrap_by_reference_view"
        ].items():
            lines.append(
                f"| {view} | {item.get('n', 0)} | "
                f"{item.get('mean', 0):+.3f} | "
                f"[{item.get('ci_low', 0):+.3f}; "
                f"{item.get('ci_high', 0):+.3f}] | "
                f"{operational['ci_excludes_zero_by_reference_view'][view]} | "
                f"{operational['equivalence_ci_inside_margin_by_reference_view'][view]} |"
            )
    op_cost = operational["cost_comparison"]
    op_gap = op_cost.get("observed_relative_difference")
    lines.extend([
        "",
        "Gates auditáveis do benchmark:",
        "",
        "| Gate | Resultado |",
        "|---|---|",
        f"| Referências completas | "
        f"{operational['reference_views_complete']} |",
        f"| Sensível à referência | "
        f"{operational['reference_sensitive']} |",
        f"| Sensível à camada | {operational['layer_sensitive']} |",
        f"| Conflito nas métricas secundárias | "
        f"{operational['secondary_conflict']} "
        f"(dominância: "
        f"{operational['secondary_dominance'].get('winner') or 'nenhuma'}) |",
        f"| Proteção estratégica (4 refs, request types) | "
        f"{operational['strategic_service_protection_grid']['passed']} "
        f"({operational['strategic_service_protection_grid']['evaluated_cells']}/"
        f"{operational['strategic_service_protection_grid']['expected_cells']}; "
        f"não avaliáveis: "
        f"{len(operational['strategic_service_protection_grid']['unevaluable_cells'])}) |",
        f"| Todos os ICs excluem zero | "
        f"{operational['ci_excludes_zero_all_reference_views']} |",
        f"| Todos os ICs inteiros na equivalência | "
        f"{operational['equivalence_ci_inside_margin']} |",
        f"| Custo disponível / vencedor / gap | "
        f"{op_cost['available_for_both']} / "
        f"{op_cost.get('winner') or 'n/d'} / "
        f"{f'{op_gap:.1%}' if op_gap is not None else 'n/d'} |",
    ])
    lines.extend([
        "",
        "| Serviço protegido | Pior margem do vencedor no benchmark | "
        "Limite |",
        "|---|---:|---:|",
    ])
    for service, loss in operational[
        "strategic_service_protection_grid"
    ]["worst_winner_minus_other_by_service"].items():
        rendered_loss = f"{loss:+.3f}" if loss is not None else "n/d"
        lines.append(
            f"| {target_by_id.get(service, {}).get('nome', service)} | "
            f"{rendered_loss} | "
            f"{-operational['strategic_service_protection']['threshold']:+.3f} |"
        )

    lines.extend([
        "",
        "### 2. Ablação justa do motor de descoberta",
        "",
        f"**{fair['code']}** (força: `{fair['strength']}`).",
        "",
        "Nos braços `*_common_*`, variam os motores K-means e LLM. Eles recebem "
        "os mesmos campos semânticos; a categoria histórica e o contexto legado "
        "são removidos, e a interface canônica e os Stages 4–6 são iguais. A "
        "LLM recebe somente um identificador técnico opaco para devolver cada "
        "atribuição; a chave Jira e seu possível sinal sequencial não entram "
        "no prompt.",
        "",
        "| Visão da referência | Cobertura | Δ Macro-F1 (LLM − K-means) | Direção |",
        "|---|---:|---:|---|",
    ])
    for view in fair["reference_view_differences"]:
        lines.append(
            f"| {view} | {fair['reference_view_coverage'].get(view, 0):.1%} | "
            f"{fair['reference_view_differences'][view]:+.3f} | "
            f"{fair['reference_view_directions'][view]} |"
        )
    fair_bootstrap = fair["bootstrap"]
    if fair_bootstrap.get("replicates"):
        lines.extend([
            "",
            f"Visão primária: `{fair['primary_reference_view']}`. "
            "Cada visão recebe bootstrap próprio:",
            "",
            "| Visão | N | Δ médio | IC 95% | Exclui zero | "
            "IC inteiro em ±0,03 |",
            "|---|---:|---:|---|---|---|",
        ])
        for view, item in fair["bootstrap_by_reference_view"].items():
            lines.append(
                f"| {view} | {item.get('n', 0)} | "
                f"{item.get('mean', 0):+.3f} | "
                f"[{item.get('ci_low', 0):+.3f}; "
                f"{item.get('ci_high', 0):+.3f}] | "
                f"{fair['ci_excludes_zero_by_reference_view'][view]} | "
                f"{fair['equivalence_ci_inside_margin_by_reference_view'][view]} |"
            )
        lines.extend([
            "",
            "| Camada | Δ Macro-F1 (LLM − K-means) | Direção |",
            "|---|---:|---|",
        ])
        for layer, difference in fair[
            "layer_differences_llm_minus_kmeans"
        ].items():
            lines.append(
                f"| {layer} | {difference:+.3f} | "
                f"{fair['layer_directions'][layer]} |"
            )

    lines.extend([
        "",
        "### Sensibilidade descritiva da margem prática",
        "",
        "A regra decisória permanece congelada em 0,03. Os demais limiares "
        "apenas mostram se a leitura depende dessa escolha.",
        "",
        "| Margem | Direção principal | Direção igual nas 4 referências | "
        "IC inteiro na faixa de equivalência |",
        "|---:|---|---|---|",
    ])
    for sensitivity_margin, item in fair[
        "margin_sensitivity_descriptive"
    ].items():
        lines.append(
            f"| {sensitivity_margin} | "
            f"{item['primary_view_direction']} | "
            f"{item['all_references_same_direction']} | "
            f"{item['all_reference_bootstrap_cis_inside_equivalence_band']} |"
        )

    lines.extend([
        "",
        "### Métricas secundárias da ablação",
        "",
        f"Dominância secundária: "
        f"`{fair['secondary_dominance'].get('winner') or 'nenhuma'}`; "
        f"conflito com a principal: `{fair['secondary_conflict']}`.",
        "",
        "| Métrica | K-means | LLM | Margem | Direção material |",
        "|---|---:|---:|---:|---|",
    ])
    for metric, item in fair["secondary_dominance"]["metrics"].items():
        lines.append(
            f"| {metric} | {item['left']:.3f} | {item['right']:.3f} | "
            f"{item['margin']:.3f} | {item['direction']} |"
        )

    lines.extend([
        "",
        "### Estabilidade entre sementes",
        "",
        f"Cubo 3 seeds × 4 referências × 3 camadas completo: "
        f"`{fair['seed_reference_layer_cube_complete']}`.",
        f"Sensível à referência: `{fair['reference_sensitive']}`; "
        f"à camada: `{fair['layer_sensitive']}`; "
        f"à seed: `{fair['seed_sensitive']}`.",
        "",
    ])
    if fair["seed_directions"]:
        lines.extend([
            "| Seed | Δ Macro-F1 (LLM − K-means) | Direção |",
            "|---:|---:|---|",
        ])
        for seed, item in fair["seed_directions"].items():
            lines.append(
                f"| {seed} | {item['difference_llm_minus_kmeans']:+.3f} | "
                f"{item['direction']} |"
            )
    else:
        lines.append("Réplicas adicionais ainda não disponíveis.")
    discordant = fair.get("discordant_grid_cells_vs_primary") or []
    lines.extend([
        "",
        "Células cuja direção difere do recorte principal "
        f"`{fair['primary_reference_view']}/final_request_types`:",
        "",
    ])
    if discordant:
        lines.extend([
            "| Seed | Referência | Camada | Δ | Direção |",
            "|---:|---|---|---:|---|",
        ])
        for cell in discordant:
            difference = cell.get("difference")
            rendered_difference = (
                f"{float(difference):+.3f}"
                if difference is not None else "n/d"
            )
            lines.append(
                f"| {cell['seed']} | {cell['view']} | {cell['layer']} | "
                f"{rendered_difference} | {cell['direction']} |"
            )
    else:
        lines.append("Nenhuma célula observada mudou de direção.")

    lines.extend([
        "",
        "## Escopo e referência automática",
        "",
        f"- Universo antes do filtro estruturado: "
        f"{report['scope']['n_total_before_filter']}",
        f"- Sala removida deterministicamente antes do Stage 1: "
        f"{report['scope']['n_sala_removed_upstream']}",
        f"- Universo do Stage 2 congelado: {report['scope']['n_total']}",
        f"- Exclusões adicionais dentro da análise: "
        f"{report['scope']['n_sala_sigilo']}",
        f"- Casos indeterminados dentro da análise: "
        f"{report['scope']['n_indeterminados']}",
        f"- Universo analítico: {report['scope']['n_analiticos']}",
        f"- Acordo estrito entre famílias de modelo: "
        f"{report['reference_quality'].get('n_consenso_estrito')} de "
        f"{report['scope']['n_analiticos']}",
        "",
        "As quatro visões (acordo estrito, cobertura total, modelo A e modelo B) "
        "precisam atingir a cobertura mínima e apontar na mesma direção para uma "
        "afirmação forte.",
        "",
        "## Catálogo histórico do Jira como baseline descritivo",
        "",
        "É o catálogo vigente na janela dos chamados, não o portfólio usado "
        "hoje. O rótulo histórico não entra na ablação; aparece apenas para "
        "mostrar se os métodos se aproximam mais do desenho adotado do que a "
        "estrutura anterior.",
        "",
        "| Visão | N | Cobertura | Macro-F1 serviços | B-cubed F1 | ARI | Reatribuição mínima |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ])
    for view, metric in report[
        "historical_jira_catalog_baseline"
    ]["views"].items():
        if "error" in metric:
            continue
        lines.append(
            f"| {view} | {metric['n']} | "
            f"{metric['n'] / max(report['scope']['n_analiticos'], 1):.1%} | "
            f"{metric['macro_best_match_f1_services']:.3f} | "
            f"{metric['bcubed_f1']:.3f} | "
            f"{metric['adjusted_rand_index']:.3f} | "
            f"{metric['minimum_reassignment_rate']:.1%} |"
        )

    lines.extend([
        "",
        "## Aderência de todas as execuções — request types",
        "",
        "| Execução | Família | Macro-F1 | B-cubed F1 | ARI | AMI | Reatribuição |",
        "|---|---|---:|---:|---:|---:|---:|",
    ])
    for run_id, run in report["runs"].items():
        metric = run["views"][fair["primary_reference_view"]][
            "final_request_types"
        ]
        if "error" in metric:
            continue
        lines.append(
            f"| {run_id} | {run['config'].get('family')} | "
            f"{metric['macro_best_match_f1_services']:.3f} | "
            f"{metric['bcubed_f1']:.3f} | "
            f"{metric['adjusted_rand_index']:.3f} | "
            f"{metric['adjusted_mutual_information']:.3f} | "
            f"{metric['minimum_reassignment_rate']:.1%} |"
        )

    lines.extend([
        "",
        "## Estabilidade alvo-independente entre réplicas",
        "",
        "Este diagnóstico usa ARI apenas entre partições do mesmo método; não "
        "usa o portfólio curado e não entra na escolha do vencedor.",
        "",
        "| Método | Camada | Pares | ARI mínimo | ARI mediano |",
        "|---|---|---:|---:|---:|",
    ])
    stability_rows = 0
    for discovery, values in report.get("stability", {}).items():
        for layer in ("discovery", "final_request_types", "final_groups"):
            layer_values = [
                float(item["ari"]) for item in values
                if item.get("layer") == layer
            ]
            if not layer_values:
                continue
            stability_rows += 1
            lines.append(
                f"| {discovery} | {layer} | {len(layer_values)} | "
                f"{min(layer_values):.3f} | "
                f"{statistics.median(layer_values):.3f} |"
            )
    if not stability_rows:
        lines.append("| n/d | n/d | 0 | n/d | n/d |")

    lines.extend([
        "",
        "## Serviços estratégicos na ablação",
        "",
        f"Células estratégicas avaliadas no cubo: "
        f"{fair['strategic_service_protection_grid']['evaluated_cells']} de "
        f"{fair['strategic_service_protection_grid']['expected_cells_for_strong_claim']}; "
        f"proteção aprovada: "
        f"`{fair['strategic_service_protection_grid']['passed']}`; "
        f"células/serviços não avaliáveis: "
        f"{len(fair['strategic_service_protection_grid']['unevaluable_cells'])}.",
        "",
        "| Serviço | Suporte | Avaliável | F1 K-means | F1 LLM | "
        "Vencedor − outro (principal) | Pior vencedor − outro no cubo |",
        "|---|---:|---|---:|---:|---:|---:|",
    ])
    for service, item in fair[
        "strategic_service_protection"
    ]["details"].items():
        name = target_by_id.get(service, {}).get("nome", service)
        worst = fair[
            "strategic_service_protection_grid"
        ]["worst_winner_minus_other_by_service"].get(service)
        rendered_worst = f"{worst:+.3f}" if worst is not None else "n/d"
        lines.append(
            f"| {name} | {min(item['kmeans_support'], item['llm_support'])} | "
            f"{item['evaluable']} | "
            f"{item['kmeans_f1']:.3f} | "
            f"{item['llm_f1']:.3f} | "
            f"{item['winner_minus_other']:+.3f} | "
            f"{rendered_worst} |"
        )

    lines.extend([
        "",
        "## Custos comparáveis",
        "",
        "O desempate usa somente o tempo da última execução bem-sucedida de todos "
        "os Stages 3–6. O consumo total de tentativas, tokens e GPU é publicado "
        "separadamente, sem escore composto. `canonicalize_stage3` integra o "
        "custo do Stage 3 nos braços comuns.",
        "",
        "| Execução | Parede 3–6 | Consumo tentado | Tokens | GPU média / p95 | VRAM pico | Energia estimada |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ])
    for run_id, run in report["runs"].items():
        cost = run["cost"]
        gpu = cost["gpu"]
        wall = (
            f"{cost['wall_seconds_stages_3_6'] / 3600:.2f} h"
            if cost["wall_seconds_stages_3_6_available"] else "n/d"
        )
        attempted = (
            f"{cost['wall_seconds_attempted_stages_3_6'] / 3600:.2f} h"
            if cost["wall_seconds_attempted_stages_3_6"] else "n/d"
        )
        tokens = (
            f"{cost['tokens']['total_tokens']:,} "
            f"({sum(cost['tokens'].get('token_count_stage_coverage', {}).values())}/4 stages)"
            if cost["tokens"].get("available") else "n/d"
        )
        gpu_util = (
            f"{gpu['utilization_mean_pct']:.1f}% / "
            f"{gpu['utilization_p95_pct']:.1f}%"
            if gpu["available"] else "n/d"
        )
        memory = (
            f"{gpu['memory_peak_mib'] / 1024:.1f} GiB"
            if gpu["available"] else "n/d"
        )
        energy = (
            f"{gpu['energy_estimated_wh']:.1f} Wh"
            if gpu["available"] else "n/d"
        )
        lines.append(
            f"| {run_id} | {wall} | {attempted} | {tokens} | {gpu_util} | "
            f"{memory} | {energy} |"
        )
    fair_cost = fair["cost_comparison"]
    op_cost = operational["cost_comparison"]

    def cost_value(value) -> str:
        return f"{float(value) / 3600:.2f} h" if value is not None else "n/d"

    def cost_gap(item: dict) -> str:
        value = item.get("observed_relative_difference")
        return f"{float(value):.1%}" if value is not None else "n/d"

    lines.extend([
        "",
        "Resumo do gate de custo (diferença material mínima: 10%):",
        "",
        "| Estimando | Esquerda | Direita | Gap | Vencedor |",
        "|---|---:|---:|---:|---|",
        f"| Benchmark downstream | "
        f"{cost_value(op_cost['aggregated_values']['m1'])} | "
        f"{cost_value(op_cost['aggregated_values']['m2'])} | "
        f"{cost_gap(op_cost)} | {op_cost.get('winner') or 'n/d'} |",
        f"| Ablação justa (medianas) | "
        f"{cost_value(fair_cost['aggregated_values']['kmeans'])} | "
        f"{cost_value(fair_cost['aggregated_values']['llm'])} | "
        f"{cost_gap(fair_cost)} | {fair_cost.get('winner') or 'n/d'} |",
    ])

    lines.extend([
        "",
        "## Leitura correta",
        "",
        "- O benchmark compara as arquiteturas downstream nos Stages 3–6 sobre "
        "o mesmo Stage 2. O M1 legado foi reexecutado com Llama e não é a "
        "resultados históricos; uma única execução não estima sua variância.",
        "- Macro-F1, B-cubed, ARI, AMI e reatribuição respondem perguntas "
        "diferentes; nenhuma delas é convertida em nota circular.",
        "- A referência automática mede estabilidade de projeção no alvo curado, "
        "não verdade objetiva nem validação externa independente.",
        "- O relatório separado de campos confronta automaticamente o que os "
        "usuários fornecem ou omitem com os campos do portfólio final.",
        "- O portfólio curado e seus campos continuam sendo a decisão estratégica "
        "adotada, qualquer que seja o vencedor metodológico.",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--config", default="experimento_config.json")
    parser.add_argument("--portfolio", default="portfolio_referencia.json")
    parser.add_argument("--rules", default="decision_rules_v1.json")
    parser.add_argument("--out-dir", default="avaliacao")
    args = parser.parse_args()

    base = Path(args.base).resolve()
    config_path = base / args.config
    portfolio_path = base / args.portfolio
    rules_path = base / args.rules
    config = _load(config_path)
    rules = _load(rules_path)
    target_by_id, service_ids, target_group_by_id = _target_metadata(
        portfolio_path
    )
    reference_path = base / "referencia" / "06_referencia_consenso.json"
    reference_metadata, reference_views = _reference_views(reference_path)
    reference_data = _load(reference_path)
    reference_rows = {
        str(row["chave"]): row
        for row in reference_data["classificacoes"]
    }
    scope = _load(base / "referencia" / "01_scope_mask.json")
    manifest = _load(base / "manifesto_insumo_comum.json")
    analytic_keys = list(reference_views["consensus_full"])
    analytic_rows = _load(base / "referencia" / "02_summaries_escopo.json")
    if analytic_keys != (scope.get("incluidos") or []):
        raise SystemExit(
            "ERRO: referencia e mascara nao possuem a mesma ordem de chaves"
        )
    excluded_keys = {
        str(item.get("chave", ""))
        for item in (scope.get("exclusoes") or []) + (scope.get("indeterminados") or [])
    }
    material_rule = rules.get("material_contingency_cell") or {}
    historical_jira_partition = {
        str(row.get("chave", "")).strip(): (
            str(row.get("tipo_atual", "")).strip() or None
        )
        for row in analytic_rows
    }
    if set(historical_jira_partition) != set(analytic_keys):
        raise SystemExit(
            "ERRO: baseline do catalogo atual diverge do universo analitico"
        )
    historical_jira_baseline = OrderedDict()
    for view_name, reference in reference_views.items():
        historical_jira_baseline[view_name] = _partition_metrics(
            historical_jira_partition,
            reference,
            service_ids,
            target_by_id,
            material_rule,
        )
    run_configs = _run_map(config, base)
    required = set(config["comparisons"]["operational"]) | set(
        config["comparisons"]["fair_ablation_primary"]
    )
    partitions = {}
    results = OrderedDict()
    warnings = []
    for run_id, run in run_configs.items():
        path = run["_path"]
        input_path = path / "02_summaries.json"
        stage3_path = path / "03_clusters.json"
        stage6_path = path / "06_classificados.json"
        if not (input_path.exists() and stage3_path.exists() and stage6_path.exists()):
            message = f"execucao incompleta ignorada: {run_id}"
            if run_id in required:
                raise SystemExit(f"ERRO: {message}")
            warnings.append(message)
            continue
        if _hash_file(input_path) != manifest["analytic_input_sha256"]:
            raise SystemExit(f"ERRO: 02 divergente em {run_id}")
        stage3 = _stage3_partition(stage3_path)
        leaf, groups, quality = _stage6_partitions(stage6_path)
        for layer_name, layer in (
            ("Stage 3", stage3),
            ("Stage 6 request types", leaf),
            ("Stage 6 grupos", groups),
        ):
            if excluded_keys & set(layer):
                raise SystemExit(
                    f"ERRO: Sala/indeterminado reapareceu em {run_id}/{layer_name}"
                )
            if set(layer) != set(analytic_keys):
                raise SystemExit(
                    f"ERRO: universo de chaves divergente em {run_id}/{layer_name}"
                )
        partitions[run_id] = {
            "discovery": stage3,
            "final_request_types": leaf,
            "final_groups": groups,
        }
        views = OrderedDict()
        for view_name, reference in reference_views.items():
            group_reference = {
                key: (
                    target_group_by_id.get(category)
                    if category is not None else None
                )
                for key, category in reference.items()
            }
            views[view_name] = {
                "discovery": _partition_metrics(
                    stage3,
                    reference,
                    service_ids,
                    target_by_id,
                    material_rule,
                ),
                "final_request_types": _partition_metrics(
                    leaf,
                    reference,
                    service_ids,
                    target_by_id,
                    material_rule,
                ),
                "final_groups": _partition_metrics(
                    groups,
                    group_reference,
                    {
                        target_group_by_id[service_id]
                        for service_id in service_ids
                    },
                    {
                        group_id: {"nome": group_id}
                        for group_id in {
                            target_group_by_id[service_id]
                            for service_id in service_ids
                        }
                    },
                    material_rule,
                ),
            }
        public_config = {
            key: value for key, value in run.items() if not key.startswith("_")
        }
        results[run_id] = {
            "config": public_config,
            "stage6_quality": quality,
            "views": views,
            "cost": _cost(path),
        }

    conclusion = _conclusion(
        results=results,
        partitions=partitions,
        run_configs=run_configs,
        config=config,
        rules=rules,
        reference_views=reference_views,
        service_ids=service_ids,
        target_by_id=target_by_id,
        material_rule=material_rule,
    )
    operational_comparison = _operational_comparison(
        results=results,
        partitions=partitions,
        config=config,
        rules=rules,
        reference_views=reference_views,
        service_ids=service_ids,
        target_by_id=target_by_id,
        material_rule=material_rule,
    )
    integrated_conclusion = _integrated_conclusion(
        operational_comparison,
        conclusion,
    )
    allowed_estimand_codes = set(rules.get("possible_conclusions") or [])
    for label, code in (
        ("ablacao", conclusion["code"]),
        ("benchmark", operational_comparison["code"]),
    ):
        if code not in allowed_estimand_codes:
            raise RuntimeError(
                f"codigo de conclusao {label} nao pre-registrado: {code}"
            )
    allowed_integrated_codes = set(
        rules.get("possible_integrated_conclusions") or []
    )
    if integrated_conclusion["code"] not in allowed_integrated_codes:
        raise RuntimeError(
            "codigo de conclusao integrada nao pre-registrado: "
            + integrated_conclusion["code"]
        )

    # Estabilidade pareada entre replicas da mesma familia.
    stability = {}
    repeats = config["comparisons"].get("fair_ablation_repeats") or {}
    for discovery, run_ids in repeats.items():
        available = [run_id for run_id in run_ids if run_id in partitions]
        values = []
        for left_id, right_id in combinations(available, 2):
            common = sorted(
                set(partitions[left_id]["discovery"])
                & set(partitions[right_id]["discovery"])
            )
            for layer in ("discovery", "final_request_types", "final_groups"):
                left_labels = [
                    partitions[left_id][layer][key] for key in common
                ]
                right_labels = [
                    partitions[right_id][layer][key] for key in common
                ]
                values.append({
                    "left": left_id,
                    "right": right_id,
                    "layer": layer,
                    "n": len(common),
                    "ari": round(
                        float(adjusted_rand_score(left_labels, right_labels)), 6
                    ),
                })
        stability[discovery] = values

    reference_quality = _load(
        base / "referencia" / "06_referencia_quality.json"
    )
    report = OrderedDict([
        ("version", VERSION),
        ("experiment_id", config.get("experiment_id")),
        ("methodological_target", "portfolio_operacional_curado_ex_post"),
        ("config_sha256", _hash_file(config_path)),
        ("rules_sha256", _hash_file(rules_path)),
        ("portfolio_sha256", _hash_file(portfolio_path)),
        (
            "operational_feedback_sha256",
            _hash_file(base / "feedback_portfolio.json"),
        ),
        (
            "package_manifest_sha256",
            _hash_file(base / "MANIFESTO_PACOTE.json"),
        ),
        (
            "protocol_sha256",
            _hash_file(base / "PROTOCOLO_METODOLOGICO.md"),
        ),
        ("input_manifest", manifest),
        ("scope", {
            "n_total": scope["metadata"]["n_total"],
            "n_total_before_filter": scope["metadata"].get(
                "n_before_upstream_filter",
                int(scope["metadata"]["n_total"])
                + int(
                    scope["metadata"].get(
                        "n_sala_removed_upstream_before_stage1",
                        scope["metadata"].get("n_sala_sigilo", 0),
                    )
                ),
            ),
            "n_sala_removed_upstream": scope["metadata"].get(
                "n_sala_removed_upstream_before_stage1",
                scope["metadata"].get("n_sala_sigilo", 0),
            ),
            "n_sala_sigilo": scope["metadata"]["n_sala_sigilo"],
            "n_indeterminados": scope["metadata"]["n_indeterminados"],
            "n_analiticos": len(analytic_keys),
            "scope_method": scope["metadata"].get(
                "scope_method", "legacy_scope_fixture"
            ),
            "llm_used_for_scope": scope["metadata"].get(
                "llm_used_for_scope"
            ),
        }),
        ("reference_metadata", reference_metadata),
        ("reference_quality", reference_quality),
        (
            "historical_jira_catalog_baseline",
            {
                "nature": (
                    "contexto_descritivo_gratuito; rotulo historico nao entra "
                    "nos bracos comuns"
                ),
                "views": historical_jira_baseline,
            },
        ),
        ("runs", results),
        ("stability", stability),
        ("operational_comparison", operational_comparison),
        ("fair_ablation_conclusion", conclusion),
        ("integrated_conclusion", integrated_conclusion),
        # Alias mantido para consumidores existentes; equivale à ablação justa.
        ("conclusion", conclusion),
        ("warnings", warnings),
        ("limitations", [
            "O portfolio foi curado ex post depois de observar sugestoes automaticas.",
            "A referencia por chamado e automatica; consenso entre modelos nao equivale a verdade.",
            "Llama e Qwen tambem participam do pipeline atual, portanto a referencia nao e plenamente independente.",
            "Descoberta e avaliacao usam a mesma janela: a aderencia e retrospectiva e in-sample.",
            "O bootstrap e condicional ao corpus e pode subestimar dependencia intra-projeto; o 02 nao possui bloco seguro para reamostragem agrupada.",
            "Os resultados descrevem um portal e uma janela temporal; generalizacao exige holdout temporal ou outro portal.",
        ]),
    ])
    out_dir = base / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "RESULTADO_COMPARACAO_ROBUSTA.metrics.json"
    md_path = out_dir / "RESULTADO_COMPARACAO_ROBUSTA.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md_path.write_text(
        _render_markdown(report, target_by_id),
        encoding="utf-8",
    )
    _pseudonymous_ledger(
        out_path=out_dir / "ledger_sanitizado.csv",
        secret_path=out_dir / ".ledger_secret",
        keys=analytic_keys,
        partitions=partitions,
        reference_views=reference_views,
        reference_rows=reference_rows,
    )
    print(f"[avaliacao] {md_path}")
    print(f"[avaliacao] {json_path}")
    print(f"[avaliacao] conclusao={conclusion['code']}")


if __name__ == "__main__":
    main()
