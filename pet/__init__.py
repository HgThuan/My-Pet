"""Gói ứng dụng Golden Fish Desktop Pet."""
from pet.app import main
from pet.config import PET_STATE_FILE, HungerState, PetStateStore
from pet.core.pet import GoldenFishPet

__all__ = ["GoldenFishPet", "HungerState", "PET_STATE_FILE", "PetStateStore", "main"]
