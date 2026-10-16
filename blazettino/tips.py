"""Loading-screen style one-liners for wipes (no LLM call: deterministic, free, easy to extend)."""
from zlib import crc32

NO_KILL = "No kill no ranking!"

TIPS = (
    "Se muori fai 0 DPS.",
    "Solo una cosa dovevate fare: portare la vita del boss a 0 prima che lui portasse a 0 la vostra.",
    "Il fuoco sul pavimento non è un tappeto di benvenuto.",
    "Resuscitare è gratis, il tempo no.",
    "Il boss ha più vita di voi: non è un caso, è il design.",
    "Le meccaniche non sono suggerimenti.",
    "Il cooldown più potente è non morire.",
    "Un wipe è solo una kill che ha preso la strada panoramica.",
    "Il prossimo pull andrà benissimo. Lo dice anche quello di prima.",
    "La barra del boss scende solo se la colpisci.",
)


def wipe_tip(seed: str) -> str:
    """Same seed, same tip (so a re-run of the same report does not reshuffle)."""
    return TIPS[crc32(seed.encode()) % len(TIPS)]
