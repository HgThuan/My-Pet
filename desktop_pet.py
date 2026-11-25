"""Điểm khởi chạy tương thích ngược cho Golden Fish Desktop Pet.

Chạy ứng dụng:
    python desktop_pet.py
"""
from __future__ import annotations

import sys

from pet.app import main
from pet.config import PET_STATE_FILE, HungerState, PetStateStore
from pet.core.pet import GoldenFishPet

__all__ = ["GoldenFishPet", "HungerState", "PET_STATE_FILE", "PetStateStore", "main"]

if __name__ == "__main__":
    sys.exit(main())
