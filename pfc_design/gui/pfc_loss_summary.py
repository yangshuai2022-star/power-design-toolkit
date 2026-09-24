"""PFC semiconductor loss rollup with explicit device counting notes."""
from __future__ import annotations

from dataclasses import dataclass

from pfc_design.engineering.device_loss import TTPLHFDeviceLoss, TTPLSlowDeviceLoss


@dataclass(frozen=True)
class PFCDeviceLossRollup:
    workpoint: str
    vin_rms_v: float
    hf: TTPLHFDeviceLoss
    slow: TTPLSlowDeviceLoss
    inductor_self_loss_w: float | None = None

    def hf_buckets(self) -> dict[str, float]:
        return {
            "hf_active_conduction_w": self.hf.active_conduction_w,
            "hf_active_switching_w": self.hf.active_switching_w,
            "hf_sr_conduction_w": self.hf.sr_conduction_w,
            "hf_sr_switching_w": self.hf.sr_switching_w,
            "hf_deadtime_reverse_w": self.hf.deadtime_reverse_w,
            "hf_coss_w": self.hf.coss_w,
            "hf_gate_drive_w": self.hf.gate_drive_w,
        }

    def slow_buckets(self) -> dict[str, float]:
        return {
            "slow_conduction_w": self.slow.conduction_w,
            "slow_gate_drive_w": self.slow.gate_drive_w,
        }

    def device_subtotal_w(self) -> float:
        return self.hf.total_w + self.slow.total_w

    def system_device_total_w(self) -> float:
        """Semiconductor-only system total (excludes magnetics inductor-self)."""
        return self.device_subtotal_w()

    def verify_sums(self, *, atol: float = 1e-9) -> tuple[bool, float, float]:
        hf_sum = sum(self.hf_buckets().values())
        slow_sum = sum(self.slow_buckets().values())
        ok = abs(hf_sum - self.hf.total_w) <= atol * max(1.0, abs(self.hf.total_w)) and abs(
            slow_sum - self.slow.total_w
        ) <= atol * max(1.0, abs(self.slow.total_w))
        return ok, hf_sum - self.hf.total_w, slow_sum - self.slow.total_w

    def format_text(self) -> str:
        lines = [
            "PFC DEVICE LOSS ROLLUP (TTPL)",
            "=" * 72,
            f"Work point : {self.workpoint} @ Vin={self.vin_rms_v:.3g} Vrms",
            "",
            "Counting notes (do not multiply these rows again):",
            "  HF half-bridge: active+SR conduction/switching already cover both",
            "    high-frequency positions for one shared MOSFET choice; Coss/gate",
            "    terms include the two-device factor used by evaluate_hf_device().",
            "  Slow leg: conduction + gate already cover the complete two-device",
            "    line-frequency leg from evaluate_slow_device().",
            "",
            f"HF device   : {self.hf.device.manufacturer} {self.hf.device.part_number}",
            f"{'Bucket':<32} {'Loss (W)':>12}",
            "-" * 46,
        ]
        for key, value in self.hf_buckets().items():
            lines.append(f"{key:<32} {value:12.5f}")
        lines.append(f"{'HF device subtotal':<32} {self.hf.total_w:12.5f}")
        lines.extend([
            "",
            f"Slow device : {self.slow.device.manufacturer} {self.slow.device.part_number}",
            f"{'Bucket':<32} {'Loss (W)':>12}",
            "-" * 46,
        ])
        for key, value in self.slow_buckets().items():
            lines.append(f"{key:<32} {value:12.5f}")
        lines.append(f"{'Slow leg subtotal':<32} {self.slow.total_w:12.5f}")
        lines.extend([
            "",
            f"{'Semiconductor system total':<32} {self.system_device_total_w():12.5f}",
        ])
        if self.inductor_self_loss_w is not None:
            lines.extend([
                f"{'Inductor-self (component)':<32} {self.inductor_self_loss_w:12.5f}",
                "Note: inductor-self loss is NOT added into semiconductor system total.",
            ])
        ok, d_hf, d_slow = self.verify_sums()
        if not ok:
            lines.append(f"WARNING: bucket mismatch Δhf={d_hf:.3e} Δslow={d_slow:.3e}")
        else:
            lines.append("Bucket sums match device subtotals.")
        return "\n".join(lines)


__all__ = ["PFCDeviceLossRollup"]
