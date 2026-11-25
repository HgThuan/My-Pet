"""Phân tích phổ âm thanh hệ thống (Equalizer/Bass Drop) và tổng hợp hiệu ứng âm thanh."""
from __future__ import annotations

import math
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import time
import wave

from PySide6.QtCore import QUrl

try:
    from PySide6.QtMultimedia import QSoundEffect
except Exception:
    QSoundEffect = None


class AudioSpectrumMonitor:
    """Bắt mức âm thanh & bass drop hệ thống (PipeWire / PulseAudio) + chế độ Demo."""

    def __init__(self):
        self.mode = "auto"  # auto | demo | off
        self.bands = [0.0] * 8
        self.level = 0.0
        self._bass_avg = 0.05
        self._beat_flag = False
        self._last_beat_t = 0.0
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._proc: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None
        self._start_capture_thread()

    def set_mode(self, mode: str):
        self.mode = mode
        if mode == "off":
            with self._lock:
                self.bands = [0.0] * 8
                self.level = 0.0
                self._beat_flag = False

    def _start_capture_thread(self):
        if not sys.platform.startswith("linux"):
            return
        cmd = self._detect_linux_monitor_cmd()
        if cmd is None:
            return
        self._thread = threading.Thread(target=self._capture_loop, args=(cmd,), daemon=True)
        self._thread.start()

    @staticmethod
    def _detect_linux_monitor_cmd() -> list[str] | None:
        if shutil.which("parec"):
            return ["parec", "--format=s16le", "--rate=8000", "--channels=1", "--latency-msec=40"]
        if shutil.which("pw-record"):
            return [
                "pw-record",
                "--raw",
                "--format=s16",
                "--rate=8000",
                "--channels=1",
                "-P",
                "{ stream.capture.sink=true }",
                "-",
            ]
        return None

    def _capture_loop(self, cmd: list[str]):
        chunk_samples = 256
        chunk_bytes = chunk_samples * 2
        low_lp = 0.0
        try:
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                bufsize=chunk_bytes,
            )
            assert self._proc.stdout is not None
            while not self._stop_event.is_set():
                raw = self._proc.stdout.read(chunk_bytes)
                if not raw or len(raw) < chunk_bytes:
                    break
                if self.mode != "auto":
                    continue
                samples = struct.unpack(f"<{chunk_samples}h", raw)
                sq_sum = 0.0
                bass_sum = 0.0
                band_acc = [0.0] * 8
                seg = chunk_samples // 8
                for i, s in enumerate(samples):
                    v = s / 32768.0
                    low_lp = low_lp * 0.86 + v * 0.14
                    sq_sum += v * v
                    bass_sum += low_lp * low_lp
                    band_acc[i // seg] += abs(v)

                rms = math.sqrt(sq_sum / chunk_samples)
                bass_rms = math.sqrt(bass_sum / chunk_samples)
                level = min(1.0, rms * 4.5)
                bass = min(1.0, bass_rms * 7.0)

                now = time.monotonic()
                is_beat = False
                if bass > 0.24 and bass > self._bass_avg * 1.75 and (now - self._last_beat_t) > 0.9:
                    is_beat = True
                    self._last_beat_t = now
                self._bass_avg = 0.92 * self._bass_avg + 0.08 * max(0.03, bass)

                bands = [min(1.0, (a / seg) * 5.2) for a in band_acc]
                with self._lock:
                    self.level = level
                    self.bands = bands
                    if is_beat:
                        self._beat_flag = True
        except Exception:
            pass
        finally:
            self._terminate_proc()

    def _terminate_proc(self):
        proc = self._proc
        self._proc = None
        if proc is not None:
            try:
                proc.terminate()
                proc.wait(timeout=0.5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
            try:
                if proc.stdout is not None:
                    proc.stdout.close()
            except Exception:
                pass

    def poll(self) -> tuple[float, list[float], bool]:
        if self.mode == "off":
            return 0.0, [0.0] * 8, False

        if self.mode == "demo":
            t = time.monotonic()
            bpm_phase = (t * 124.0 / 60.0) % 1.0
            kick = math.exp(-bpm_phase * 8.0)
            bands = [
                max(0.08, min(1.0, kick * (0.95 - i * 0.07) + 0.28 * abs(math.sin(t * (3.2 + i * 1.1) + i))))
                for i in range(8)
            ]
            level = sum(bands) / 8.0
            beat = False
            if bpm_phase < 0.06 and (t - self._last_beat_t) > 1.8:
                beat = True
                self._last_beat_t = t
            return level, bands, beat

        with self._lock:
            beat = self._beat_flag
            self._beat_flag = False
            return self.level, list(self.bands), beat

    def stop(self):
        self._stop_event.set()
        self._terminate_proc()


class SoundPlayer:
    """Tổng hợp sẵn âm thanh 'bụp' (pop), 'tõm' (splash), khóa lồng 'cạch' và uốn cong kim loại."""

    def __init__(self):
        self._paths: dict[str, str] = {}
        self._effects: dict[str, object] = {}
        self._build_pop()
        self._build_splash()
        self._build_cage_lock()
        self._build_metal_bend()

    def _write_wav(self, name: str, frames: bytes, sample_rate: int = 22050):
        try:
            fd, path = tempfile.mkstemp(prefix=f"fish_{name}_", suffix=".wav")
            os.close(fd)
            with wave.open(path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(frames)
            self._paths[name] = path
            if QSoundEffect is not None:
                eff = QSoundEffect()
                eff.setSource(QUrl.fromLocalFile(path))
                eff.setVolume(0.55)
                self._effects[name] = eff
        except Exception:
            pass

    def _build_pop(self):
        sr = 22050
        n = int(sr * 0.095)
        frames = bytearray()
        for i in range(n):
            t = i / sr
            p = i / n
            freq = 260.0 + 620.0 * (p ** 1.4)
            env = math.sin(math.pi * p) * math.exp(-p * 3.8)
            val = int(max(-1.0, min(1.0, math.sin(2 * math.pi * freq * t) * env * 0.65)) * 32767)
            frames.extend(struct.pack("<h", val))
        self._write_wav("pop", bytes(frames), sr)

    def _build_splash(self):
        sr = 22050
        n = int(sr * 0.22)
        frames = bytearray()
        for i in range(n):
            t = i / sr
            p = i / n
            # Tiếng "tõm" nước: giọt rơi hạ tần rồi vút lên + bọt khí nhẹ
            freq = 520.0 - 260.0 * p + 420.0 * (p ** 2.2)
            env = math.sin(math.pi * p) * math.exp(-p * 2.5)
            w = math.sin(2 * math.pi * freq * t) + 0.25 * math.sin(2 * math.pi * freq * 2.3 * t)
            val = int(max(-1.0, min(1.0, w * env * 0.52)) * 32767)
            frames.extend(struct.pack("<h", val))
        self._write_wav("splash", bytes(frames), sr)

    def _build_cage_lock(self):
        """Tổng hợp tiếng lồng sắt rơi nhẹ + chốt khóa 'cạch' kim loại."""
        sr = 22050
        n = int(sr * 0.25)
        frames = bytearray()
        # LCG giả ngẫu nhiên nhẹ để tạo xung nhiễu kim loại ngắn (không cần random import)
        seed = 1337
        for i in range(n):
            t = i / sr
            seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
            noise = (seed / 0x3FFFFFFF) - 1.0

            # Nhịp 1 (t = 0.00s): tiếng khung sắt chạm xuống ("keng" trầm nhẹ)
            env1 = math.exp(-t * 28.0)
            clang1 = (
                0.50 * math.sin(2 * math.pi * 410.0 * t)
                + 0.35 * math.sin(2 * math.pi * 1085.0 * t)
                + 0.20 * math.sin(2 * math.pi * 1790.0 * t)
            ) * env1

            # Nhịp 2 (t = 0.065s): tiếng chốt khóa "cạch!" sắc gọn
            t2 = t - 0.065
            latch = 0.0
            if t2 >= 0.0:
                env2 = math.exp(-t2 * 45.0)
                snap = math.exp(-t2 * 140.0) * noise * 0.55
                ring = (
                    0.48 * math.sin(2 * math.pi * 1420.0 * t2)
                    + 0.34 * math.sin(2 * math.pi * 2380.0 * t2)
                    + 0.22 * math.sin(2 * math.pi * 3410.0 * t2)
                ) * env2
                latch = ring + snap

            w = (clang1 * 0.55 + latch * 0.78) * 0.68
            val = int(max(-1.0, min(1.0, w)) * 32767)
            frames.extend(struct.pack("<h", val))
        self._write_wav("cage_lock", bytes(frames), sr)

    def _build_metal_bend(self):
        """Tổng hợp âm thanh kim loại rên rỉ uốn cong và bật tách thanh sắt."""
        sr = 22050
        n = int(sr * 0.58)
        frames = bytearray()
        phase1 = 0.0
        phase2 = 0.0
        phase3 = 0.0
        seed = 4242
        for i in range(n):
            t = i / sr
            p = i / n
            seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
            noise = (seed / 0x3FFFFFFF) - 1.0

            # Tiếng rít/uốn thanh sắt tăng dần ứng suất với rung FM kim loại
            strain_wobble = math.sin(2 * math.pi * 19.0 * t) * (18.0 + 35.0 * p)
            f1 = 195.0 + 360.0 * (p ** 1.35) + strain_wobble
            f2 = f1 * 2.76  # họa âm phi điều hòa đặc trưng của kim loại
            f3 = f1 * 4.43
            phase1 += (2 * math.pi * f1) / sr
            phase2 += (2 * math.pi * f2) / sr
            phase3 += (2 * math.pi * f3) / sr

            env_creak = math.sin(math.pi * min(1.0, p / 0.88)) * (0.45 + 0.55 * p)
            creak = (
                0.50 * math.sin(phase1)
                + 0.32 * math.sin(phase2)
                + 0.18 * math.sin(phase3)
            ) * env_creak

            # Cú bật/gãy thanh sắt ở cuối (p >= 0.76)
            t_snap = t - 0.44
            snap = 0.0
            if t_snap >= 0.0:
                s_env = math.exp(-t_snap * 24.0)
                snap = (
                    0.55 * math.sin(2 * math.pi * 880.0 * t_snap)
                    + 0.40 * math.sin(2 * math.pi * 1640.0 * t_snap)
                    + 0.30 * math.exp(-t_snap * 90.0) * noise
                ) * s_env

            w = (creak * 0.62 + snap * 0.72) * 0.65
            val = int(max(-1.0, min(1.0, w)) * 32767)
            frames.extend(struct.pack("<h", val))
        self._write_wav("metal_bend", bytes(frames), sr)

    def _play(self, name: str):
        eff = self._effects.get(name)
        if eff is not None:
            try:
                eff.play()  # type: ignore[attr-defined]
                return
            except Exception:
                pass
        path = self._paths.get(name)
        if not path:
            return
        if sys.platform.startswith("linux") and shutil.which("aplay"):
            try:
                subprocess.Popen(
                    ["aplay", "-q", path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception:
                pass
        elif sys.platform == "darwin" and shutil.which("afplay"):
            try:
                subprocess.Popen(
                    ["afplay", path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception:
                pass

    def play_pop(self):
        self._play("pop")

    def play_splash(self):
        self._play("splash")

    def play_cage_lock(self):
        self._play("cage_lock")

    def play_metal_bend(self):
        self._play("metal_bend")

    def cleanup(self):
        for path in self._paths.values():
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass
        self._paths.clear()


