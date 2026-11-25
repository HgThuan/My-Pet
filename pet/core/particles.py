"""Hệ thống sinh & cập nhật vật lý cho các hạt hiệu ứng cục bộ và overlay toàn vùng."""
from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

from PySide6.QtGui import QColor

from pet.config import RAINBOW_COLORS, SIZE
from pet.models import Particle

if TYPE_CHECKING:
    from pet.core.pet import GoldenFishPet


class ParticleSystem:
    """Quản lý sinh hạt (bong bóng, sao, tim, vụn giấy, tia lửa, bong bóng cầu vồng...) và cập nhật vòng đời."""

    def __init__(self, pet: GoldenFishPet):
        self.pet = pet

    def spawn(self, kind: str, x: float | None = None, y: float | None = None) -> None:
        pet = self.pet
        cx = SIZE / 2.0 if x is None else x
        cy = SIZE / 2.0 if y is None else y

        if kind == "bubble":
            if x is None and y is None:
                if random.random() < 0.68:
                    bx, by = pet._mouth_local_pos()
                    bx += random.uniform(-4.0, 4.0)
                    by += random.uniform(-4.0, 2.0)
                else:
                    bx, by = pet._tail_tip_local_pos()
                    bx += random.uniform(-5.0, 5.0)
                    by += random.uniform(-6.0, 4.0)
            else:
                bx, by = cx, cy
            pet.particles.append(Particle(
                kind="bubble",
                x=bx,
                y=by,
                vx=-pet.vx * 0.14 + random.uniform(-0.28, 0.28),
                vy=random.uniform(-1.35, -0.70),
                life=62, max_life=62,
                size=random.uniform(4.8, 9.8),
                color=QColor(220, 248, 255, 170),
            ))
        elif kind == "trail_bubble":
            tx, ty = pet._tail_tip_local_pos()
            pet.particles.append(Particle(
                kind="trail_bubble",
                x=tx + random.uniform(-6, 6),
                y=ty + random.uniform(-6, 6),
                vx=-pet.vx * 0.16 + random.uniform(-0.35, 0.35),
                vy=-pet.vy * 0.16 + random.uniform(-0.6, -0.15),
                life=34, max_life=34,
                size=random.uniform(4.5, 8.5),
                color=QColor(225, 250, 255, 185),
            ))
        elif kind == "rainbow_bubble":
            mx, my = pet._mouth_local_pos()
            gx = pet.px + mx + random.uniform(-6.0, 6.0)
            gy = pet.py + my + random.uniform(-5.0, 5.0)
            pet.particle_overlay.spawn(
                kind="rainbow_bubble",
                gx=gx,
                gy=gy,
                vx=pet.direction * random.uniform(2.2, 5.0) + random.uniform(-0.8, 0.8),
                vy=random.uniform(-2.6, 0.8),
                life=72,
                size=random.uniform(8.0, 15.0),
                color=random.choice(RAINBOW_COLORS),
            )
        elif kind == "dizzy_bubble":
            fcx, fcy = pet.center_global()
            ang = random.uniform(0.0, math.tau)
            spd = random.uniform(1.8, 4.4)
            pet.particle_overlay.spawn(
                kind="bubble",
                gx=fcx + math.cos(ang) * random.uniform(14.0, 32.0),
                gy=fcy + math.sin(ang) * random.uniform(14.0, 28.0),
                vx=math.cos(ang) * spd,
                vy=math.sin(ang) * spd - 0.6,
                life=52,
                size=random.uniform(6.0, 12.0),
                color=QColor(215, 246, 255, 185),
            )
        elif kind == "dizzy_star":
            fcx, fcy = pet.center_global()
            ang = random.uniform(0.0, math.tau)
            spd = random.uniform(1.6, 3.8)
            pet.particle_overlay.spawn(
                kind="star",
                gx=fcx + math.cos(ang) * random.uniform(18.0, 34.0),
                gy=fcy - 12.0 + math.sin(ang) * random.uniform(10.0, 22.0),
                vx=math.cos(ang) * spd,
                vy=math.sin(ang) * spd - 0.8,
                life=44,
                size=random.uniform(7.5, 11.5),
                color=QColor("#ffd166"),
            )
        elif kind == "water_drop":
            mx, my = pet._mouth_local_pos()
            pet.particles.append(Particle(
                kind="water_drop",
                x=mx if x is None else x,
                y=my if y is None else y,
                vx=pet.direction * random.uniform(3.2, 6.2),
                vy=random.uniform(-2.6, 1.4),
                life=30, max_life=30,
                size=random.uniform(7.0, 10.5),
                color=QColor("#72efdd"),
            ))
        elif kind == "boil":
            pet.particles.append(Particle(
                kind="boil",
                x=cx + random.uniform(-52, 52),
                y=cy + random.uniform(10, 48),
                vx=random.uniform(-0.6, 0.6),
                vy=random.uniform(-3.6, -1.9),
                life=34, max_life=34,
                size=random.uniform(6.0, 14.0),
                color=QColor(255, 232, 214, 175),
            ))
        elif kind == "puff_air":
            ang = math.atan2(-pet.vy, -pet.vx) + random.uniform(-0.35, 0.35)
            spd = random.uniform(2.5, 4.8)
            pet.particles.append(Particle(
                kind="puff_air",
                x=cx + math.cos(ang) * 18,
                y=cy + math.sin(ang) * 18,
                vx=math.cos(ang) * spd,
                vy=math.sin(ang) * spd,
                life=24, max_life=24,
                size=random.uniform(6.0, 11.0),
                color=QColor(235, 250, 255, 200),
            ))
        elif kind == "heart":
            pet.particles.append(Particle(
                kind="heart",
                x=cx + random.uniform(-26, 26),
                y=cy - 24 + random.uniform(-8, 8),
                vx=random.uniform(-0.4, 0.4),
                vy=random.uniform(-1.3, -0.7),
                life=55, max_life=55,
                size=random.uniform(8, 12),
                color=QColor("#ff4d6d"),
            ))
        elif kind == "ghost":
            pet.particles.append(Particle(
                kind="ghost",
                x=cx + random.uniform(-14, 14),
                y=cy - 26,
                vx=random.uniform(-0.18, 0.18),
                vy=random.uniform(-0.85, -0.50),
                life=78, max_life=78,
                size=random.uniform(13.0, 17.0),
                color=QColor(225, 244, 255, 195),
            ))
        elif kind == "zzz":
            pet.particles.append(Particle(
                kind="zzz",
                x=cx + 28 * (-pet.direction),
                y=cy - 34,
                vx=0.25 * (-pet.direction),
                vy=-0.55,
                life=75, max_life=75,
                size=random.uniform(11, 15),
                color=QColor("#4361ee"),
            ))
        elif kind == "star":
            pet.particles.append(Particle(
                kind="star",
                x=cx + random.uniform(-32, 32),
                y=cy - 18 + random.uniform(-16, 12),
                vx=random.uniform(-1.4, 1.4),
                vy=random.uniform(-1.8, -0.5),
                life=42, max_life=42,
                size=random.uniform(7, 11),
                color=QColor("#ffd166"),
            ))
        elif kind == "excl":
            pet.particles.append(Particle(
                kind="excl",
                x=cx + 26 * pet.direction,
                y=cy - 38,
                vx=0.0, vy=-0.45,
                life=42, max_life=42,
                size=16, color=QColor("#ff595e"),
            ))
        elif kind == "anger":
            pet.particles.append(Particle(
                kind="anger",
                x=cx + 32 * (-pet.direction),
                y=cy - 34,
                vx=0.0, vy=-0.12,
                life=55, max_life=55,
                size=15, color=QColor("#e63946"),
            ))
        elif kind == "sweat":
            pet.particles.append(Particle(
                kind="sweat",
                x=cx - 30 * pet.direction,
                y=cy - 18,
                vx=0.0, vy=0.35,
                life=45, max_life=45,
                size=9, color=QColor("#4cc9f0"),
            ))
        elif kind == "crumb":
            mx, my = pet._mouth_local_pos()
            pet.particles.append(Particle(
                kind="crumb",
                x=mx + random.uniform(-6, 6),
                y=my + random.uniform(-4, 4),
                vx=pet.direction * random.uniform(1.0, 2.8) + random.uniform(-0.8, 0.8),
                vy=random.uniform(-2.6, -0.6),
                life=32, max_life=32,
                size=random.uniform(5.0, 8.5),
                color=random.choice([QColor("#ffffff"), QColor("#dce6f2"), QColor("#ffca3a")]),
            ))
        elif kind == "spark":
            ang = random.uniform(0.0, math.tau)
            spd = random.uniform(2.8, 6.4)
            pet.particles.append(Particle(
                kind="spark",
                x=cx + random.uniform(-4, 4),
                y=cy + random.uniform(-4, 4),
                vx=math.cos(ang) * spd,
                vy=math.sin(ang) * spd - 1.2,
                life=20, max_life=20,
                size=random.uniform(7.5, 13.5),
                color=random.choice([QColor("#fff3a3"), QColor("#ffbe0b"), QColor("#ff6b35")]),
            ))
        elif kind == "smoke":
            pet.particles.append(Particle(
                kind="smoke",
                x=cx + random.uniform(-14, 14),
                y=cy + random.uniform(-10, 10),
                vx=random.uniform(-1.3, 1.3),
                vy=random.uniform(-1.6, -0.4),
                life=32, max_life=32,
                size=random.uniform(6.5, 12.0),
                color=random.choice([QColor(215, 222, 230, 175), QColor(185, 195, 206, 165)]),
            ))
        elif kind == "tear":
            pet.particles.append(Particle(
                kind="tear",
                x=cx + random.choice([-14.0, 14.0]) + random.uniform(-2, 2),
                y=cy + 6.0,
                vx=random.uniform(-0.4, 0.4),
                vy=random.uniform(0.6, 1.4),
                life=32, max_life=32,
                size=random.uniform(6.0, 8.2),
                color=QColor("#9ce8ff"),
            ))

    def update(self) -> None:
        pet = self.pet
        alive: list[Particle] = []
        for pt in pet.particles:
            pt.x += pt.vx
            pt.y += pt.vy
            if pt.kind == "bubble":
                pt.x += math.sin(pet.frame * 0.14 + pt.size) * 0.34
                pt.vx *= 0.96
                pt.size += 0.045
            elif pt.kind == "trail_bubble":
                pt.vx *= 0.94
                pt.vy *= 0.96
                pt.size += 0.09
            elif pt.kind == "rainbow_bubble":
                pt.vx *= 0.97
                pt.vy -= 0.02
                pt.x += math.sin(pet.frame * 0.18 + pt.size) * 0.35
                pt.size += 0.07
            elif pt.kind == "water_drop":
                pt.vy += 0.16
            elif pt.kind == "crumb":
                pt.vy += 0.14
            elif pt.kind == "spark":
                pt.vx *= 0.92
                pt.vy += 0.18
            elif pt.kind == "smoke":
                pt.vx *= 0.94
                pt.vy *= 0.95
                pt.size += 0.22
            elif pt.kind == "tear":
                pt.vy += 0.11
            elif pt.kind == "ghost":
                pt.x += math.sin(pet.frame * 0.10 + pt.size) * 0.38
            elif pt.kind == "sweat":
                pt.vy += 0.05
            pt.life -= 1
            if pt.life > 0:
                alive.append(pt)
        pet.particles = alive
