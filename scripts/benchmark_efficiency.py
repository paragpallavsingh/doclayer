"""
Benchmark and Efficiency Test Suite for doclayer.
Measures parsing latency, validation throughput, Git-diff resolution speed,
and large-scale repository stress performance (500+ subsystem layers).
"""
import sys
from pathlib import Path

# Ensure root directory is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

import tempfile
import time
import tracemalloc
from typing import Dict, List

from doclayer.parser import parse_layer_file, extract_invariants_fence, parse_invariants_toml
from doclayer.validator import validate_file, validate_layer_doc
from doclayer.cli import resolve_layers_for_changed_files


def benchmark_single_layer_parse(layer_path: Path, iterations: int = 1000) -> Dict:
    """Measures single-layer parsing and invariant extraction latency."""
    latencies_us: List[float] = []
    
    for _ in range(iterations):
        t0 = time.perf_counter()
        doc = parse_layer_file(layer_path)
        t1 = time.perf_counter()
        latencies_us.append((t1 - t0) * 1_000_000)

    latencies_us.sort()
    avg_us = sum(latencies_us) / len(latencies_us)
    p50_us = latencies_us[int(len(latencies_us) * 0.50)]
    p95_us = latencies_us[int(len(latencies_us) * 0.95)]
    p99_us = latencies_us[int(len(latencies_us) * 0.99)]
    
    return {
        "iterations": iterations,
        "avg_us": avg_us,
        "p50_us": p50_us,
        "p95_us": p95_us,
        "p99_us": p99_us,
        "ops_per_sec": 1_000_000 / avg_us if avg_us > 0 else 0,
    }


def benchmark_validation_throughput(layer_path: Path, iterations: int = 1000) -> Dict:
    """Measures full validation throughput."""
    doc = parse_layer_file(layer_path)
    latencies_us: List[float] = []

    for _ in range(iterations):
        t0 = time.perf_counter()
        report = validate_layer_doc(doc)
        t1 = time.perf_counter()
        latencies_us.append((t1 - t0) * 1_000_000)

    latencies_us.sort()
    avg_us = sum(latencies_us) / len(latencies_us)
    p95_us = latencies_us[int(len(latencies_us) * 0.95)]

    return {
        "iterations": iterations,
        "avg_us": avg_us,
        "p95_us": p95_us,
        "validations_per_sec": 1_000_000 / avg_us if avg_us > 0 else 0,
    }


SAMPLE_SUBSYSTEM_MD = """# Subsystem: Kubernetes Policy & Admission Governance

**Package:** `src/modules/k8s_policy/`
**Owner:** `@platform-sec` (Alerts: `EP-KUBE-POLICY-TIER1`)

---

## 1. Overview & Topology
Admission webhook controller and dynamic policy enforcement engine for multi-tenant Kubernetes clusters.

```
[K8s API Request] ──> [DocLayer Webhook Validator] ──> [Etcd Admission State]
```

---

## 2. Contracts & Invariants

```invariants
[invariants]
max_webhook_timeout_seconds = 3
minimum_run_as_user = 10001
allow_privileged_escalation = false

[targets]
admission_latency_target_ms = 25

[dependencies]
upstream = ["k8s-api-server", "ingress-controller"]
downstream = ["vault-agent", "audit-webhook"]
state_dependencies = ["admission_cache"]
identity_invariants = ["cluster_id_immutable"]
safety_firewalls = ["never_bypass_namespace_isolation"]
```

| Invariant / Contract | Why & Rationale | Reference | Evidence Anchor |
| :--- | :--- | :--- | :--- |
| `max_webhook_timeout_seconds = 3` | Prevent kube-apiserver admission timeout failure | `RFC-204` | `src/modules/k8s_policy/constants.py` |
| `minimum_run_as_user = 10001` | Enforce non-root execution policy across all pods | `CIS-BENCHMARK-5.2` | `src/modules/k8s_policy/constants.py` |
| `allow_privileged_escalation = false` | Prohibit container privilege escalation | `ADR-041` | `src/modules/k8s_policy/constants.py` |

---

## 3. Failure Modes & Agent Safety Runbook

| Symptom / Error | Probable Root Cause | Safe Remediation | Prohibited Actions (What NOT to do) | Reference |
| :--- | :--- | :--- | :--- | :--- |
| `ERR_ADMISSION_TIMEOUT` | Webhook latency exceeded SLA | Inspect audit log lag | NEVER disable admission webhook controller in production | `INC-3301` |

---

## 4. References
* Implementation: `src/modules/k8s_policy/`
* Incidents: `INC-3301`
"""


def benchmark_scalability_stress(scale_counts: List[int] = [50, 100, 500]) -> List[Dict]:
    """Generates synthetic subsystem layers to measure scaling latency and memory usage."""
    results = []
    template_doc = SAMPLE_SUBSYSTEM_MD

    for count in scale_counts:
        with tempfile.TemporaryDirectory() as tmp_dir:
            layers_dir = Path(tmp_dir) / ".doclayer"
            layers_dir.mkdir(parents=True, exist_ok=True)

            # Create N layer files
            for i in range(count):
                layer_file = layers_dir / f"service_{i:04d}.md"
                content = template_doc.replace("Kubernetes Policy & Admission Governance", f"Synthetic Subsystem #{i}")
                content = content.replace("src/modules/k8s_policy/", f"src/modules/service_{i:04d}/")
                layer_file.write_text(content, encoding="utf-8")

            # Measure full directory scan & validation
            tracemalloc.start()
            t0 = time.perf_counter()

            all_files = sorted(layers_dir.glob("*.md"))
            passed = sum(1 for f in all_files if validate_file(f).is_valid)

            t1 = time.perf_counter()
            current_mem, peak_mem = tracemalloc.get_traced_memory()
            tracemalloc.stop()

            total_ms = (t1 - t0) * 1000
            throughput = count / (t1 - t0) if (t1 - t0) > 0 else 0

            # Measure targeted git resolution
            t_git_0 = time.perf_counter()
            changed_mock = [f"src/modules/service_{count//2:04d}/router.py"]
            matched = resolve_layers_for_changed_files(layers_dir, changed_mock)
            t_git_1 = time.perf_counter()
            git_resolve_ms = (t_git_1 - t_git_0) * 1000

            results.append({
                "subsystem_count": count,
                "passed_count": passed,
                "total_scan_ms": total_ms,
                "throughput_layers_per_sec": throughput,
                "peak_memory_kb": peak_mem / 1024,
                "git_targeted_resolve_ms": git_resolve_ms,
                "targeted_match_count": len(matched),
            })

    return results


def run_all_benchmarks():
    print("=" * 70)
    print(" doclayer Performance & Efficiency Benchmark Suite")
    print("=" * 70)

    with tempfile.NamedTemporaryFile("w+", suffix=".md", delete=False, encoding="utf-8") as tf:
        tf.write(SAMPLE_SUBSYSTEM_MD)
        tf.flush()
        spec_doc = Path(tf.name)

    try:
        # Benchmark 1: Parsing
        print("\n[1] Micro-Benchmark: Single Layer Parser & Invariant Extractor")
        parse_metrics = benchmark_single_layer_parse(spec_doc, iterations=1000)
        print(f"  * Iterations:      {parse_metrics['iterations']:,}")
        print(f"  * Avg Latency:     {parse_metrics['avg_us']:.2f} us ({parse_metrics['avg_us']/1000:.3f} ms)")
        print(f"  * P50 (Median):    {parse_metrics['p50_us']:.2f} us")
        print(f"  * P95 Latency:     {parse_metrics['p95_us']:.2f} us")
        print(f"  * P99 Latency:     {parse_metrics['p99_us']:.2f} us")
        print(f"  * Parse Speed:     {parse_metrics['ops_per_sec']:,.0f} layers/second")

        # Benchmark 2: Validation
        print("\n[2] Micro-Benchmark: Invariant Schema & Contract Validation")
        val_metrics = benchmark_validation_throughput(spec_doc, iterations=1000)
        print(f"  * Avg Latency:     {val_metrics['avg_us']:.2f} us")
        print(f"  * P95 Latency:     {val_metrics['p95_us']:.2f} us")
        print(f"  * Throughput:      {val_metrics['validations_per_sec']:,.0f} validations/second")

        # Benchmark 3: Scalability Stress Test
        print("\n[3] Scalability & Monorepo Scaling Stress Test (50, 100, 500 Subsystems)")
        print("-" * 88)
        print(f"| {'Subsystems':<12} | {'Full Scan (ms)':<15} | {'Throughput (ops/s)':<20} | {'Peak Mem (KB)':<14} | {'Git Resolve (ms)':<18} |")
        print("-" * 88)

        stress_results = benchmark_scalability_stress([50, 100, 500])
        for res in stress_results:
            print(
                f"| {res['subsystem_count']:<12} "
                f"| {res['total_scan_ms']:<15.2f} "
                f"| {res['throughput_layers_per_sec']:<20.0f} "
                f"| {res['peak_memory_kb']:<14.2f} "
                f"| {res['git_targeted_resolve_ms']:<18.2f} |"
            )
        print("-" * 88)

        print("\n" + "=" * 70)
        print(" [OK] Benchmark Suite Complete.")
        print("=" * 70)
    finally:
        if spec_doc.exists():
            try:
                spec_doc.unlink()
            except Exception:
                pass


if __name__ == "__main__":
    run_all_benchmarks()
