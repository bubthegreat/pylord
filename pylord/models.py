import hashlib
import hmac
import os
from dataclasses import dataclass

SCRYPT_N = 16384
SCRYPT_R = 8
SCRYPT_P = 1
SALT_BYTES = 16


def hash_password(pw: str) -> str:
    """Hash a password with scrypt, embedding a random salt.

    Format: scrypt$<salt_hex>$<hash_hex>
    """
    salt = os.urandom(SALT_BYTES)
    derived = hashlib.scrypt(
        pw.encode("utf-8"), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P
    )
    return f"scrypt${salt.hex()}${derived.hex()}"


def verify_password(pw: str, hashed: str) -> bool:
    """Verify a password against a scrypt$<salt_hex>$<hash_hex> hash."""
    try:
        algo, salt_hex, hash_hex = hashed.split("$")
    except ValueError:
        return False
    if algo != "scrypt":
        return False
    salt = bytes.fromhex(salt_hex)
    expected = bytes.fromhex(hash_hex)
    derived = hashlib.scrypt(
        pw.encode("utf-8"), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P
    )
    return hmac.compare_digest(derived, expected)


@dataclass
class Player:
    id: int | None
    name: str
    password_hash: str
    gender: str = "M"
    class_type: int = 1
    level: int = 1
    exp: int = 1
    hp: int = 20
    hp_max: int = 20
    strength: int = 10
    defense: int = 1
    charm: int = 1
    gold: int = 500
    bank: int = 0
    gems: int = 0
    weapon_num: int = 1
    armor_num: int = 1
    forest_fights: int = 15
    player_fights: int = 3
    flirts_today: int = 0
    alive: int = 1
    at_inn: int = 0
    seen_master: int = 0
    seen_dragon: int = 0
    seen_violet: int = 0
    seen_bard: int = 0
    married_to: int | None = None
    lays: int = 0
    kids: int = 0
    king_count: int = 0
    skill_dk: int = 0
    skill_my: int = 0
    skill_th: int = 0
    skill_uses: int = 0
    horse: int = 0
    last_played: str = ""
    online: int = 0
    # Migration 2 -- see pylord/db.py's MIGRATIONS[1] for what each gates.
    high_spirits: int = 0
    weird: int = 0
    has_fairy: int = 0
    fairy_lore: int = 0
    amulet: int = 0
    pvp_kills: int = 0
    magically_delicious: int = 0
    divorced: int = 0
    mastered_dk: int = 0
    mastered_my: int = 0
    mastered_th: int = 0
    # Migration 3 -- trainable fight capacity and the regeneration clock.
    # See pylord/engine/fights.py.
    fight_bonus: int = 0
    endurance_bought: int = 0
    fights_regen_at: str = ""
    description1: str = ""
    description2: str = ""
