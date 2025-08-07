from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple
from math import floor
import swisseph as swe
from timezonefinder import TimezoneFinder
from pytz import timezone

swe.set_ephe_path("./ephe")

# === Constants ===
ZODIAC_SIGNS = [
    "Aries",
    "Taurus",
    "Gemini",
    "Cancer",
    "Leo",
    "Virgo",
    "Libra",
    "Scorpio",
    "Sagittarius",
    "Capricorn",
    "Aquarius",
    "Pisces",
]

PLANETS = {
    "Sun": swe.SUN,
    "Moon": swe.MOON,
    "Mars": swe.MARS,
    "Mercury": swe.MERCURY,
    "Jupiter": swe.JUPITER,
    "Venus": swe.VENUS,
    "Saturn": swe.SATURN,
    "Rahu": swe.MEAN_NODE,
    "Ketu": swe.MEAN_NODE,  # 180° opposite of Rahu
}


# Nakshatra and Dasha info
NAKSHATRAS = [
    "Ashwini",
    "Bharani",
    "Krittika",
    "Rohini",
    "Mrigashira",
    "Ardra",
    "Punarvasu",
    "Pushya",
    "Ashlesha",
    "Magha",
    "Purva Phalguni",
    "Uttara Phalguni",
    "Hasta",
    "Chitra",
    "Swati",
    "Vishakha",
    "Anuradha",
    "Jyeshtha",
    "Mula",
    "Purva Ashadha",
    "Uttara Ashadha",
    "Shravana",
    "Dhanishta",
    "Shatabhisha",
    "Purva Bhadrapada",
    "Uttara Bhadrapada",
    "Revati",
]

DASHA_SEQUENCE = [
    ("Ketu", 7),
    ("Venus", 20),
    ("Sun", 6),
    ("Moon", 10),
    ("Mars", 7),
    ("Rahu", 18),
    ("Jupiter", 16),
    ("Saturn", 19),
    ("Mercury", 17),
]

# Mapping Nakshatra index to Dasha lord
NAKSHATRA_TO_DASHA_LORD = [
    seq[0] for seq in DASHA_SEQUENCE
] * 3  # repeats after every 9

# Nakshatra span in degrees
NAKSHATRA_SPAN = 13 + 1 / 3  # 13.333...


TITHIS = [
    "Pratipada",
    "Dvitiya",
    "Tritiya",
    "Chaturthi",
    "Panchami",
    "Shashthi",
    "Saptami",
    "Ashtami",
    "Navami",
    "Dashami",
    "Ekadashi",
    "Dvadashi",
    "Trayodashi",
    "Chaturdashi",
    "Purnima / Amavasya",
] * 2

KARANAS = [
    "Bava",
    "Balava",
    "Kaulava",
    "Taitila",
    "Garaja",
    "Vanija",
    "Vishti",
    "Bava",
    "Balava",
    "Kaulava",
    "Taitila",
    "Garaja",
    "Vanija",
    "Vishti",
    "Shakuni",
    "Chatushpada",
    "Naga",
    "Kimstughna",
]

YOGAS = [
    "Vishkambha",
    "Priti",
    "Ayushman",
    "Saubhagya",
    "Shobhana",
    "Atiganda",
    "Sukarma",
    "Dhriti",
    "Shoola",
    "Ganda",
    "Vriddhi",
    "Dhruva",
    "Vyaghata",
    "Harshana",
    "Vajra",
    "Siddhi",
    "Vyatipata",
    "Variyana",
    "Parigha",
    "Shiva",
    "Siddha",
    "Sadhya",
    "Shubha",
    "Shukla",
    "Brahma",
    "Indra",
    "Vaidhriti",
]

VARGA_DIVISIONS = {
    "D1": 1,
    "D2": 2,
    "D3": 3,
    "D4": 4,
    "D5": 5,
    "D6": 6,
    "D7": 7,
    "D8": 8,
    "D9": 9,
    "D10": 10,
    "D11": 11,
    "D12": 12,
    "D16": 16,
    "D20": 20,
    "D24": 24,
    "D30": 30,
}


# === Data Classes ===
@dataclass
class Planet:
    name: str
    longitude: float
    sign: str
    retrograde: bool


@dataclass
class House:
    number: int
    sign: str
    planets: List[str] = field(default_factory=list)


@dataclass
class Chart:
    ascendant_sign: str
    ascendant_degree: float
    houses: List[House]
    planets: Dict[str, Planet]
    chart_type: str = "D1"


# === Core Functions ===


def get_timezone_offset(lat: float, lon: float, birth_datetime_str: str) -> float:
    birth_datetime = datetime.fromisoformat(birth_datetime_str)
    tf = TimezoneFinder()
    tz_name = tf.timezone_at(lng=lon, lat=lat)
    time_offset = 5.5  # default for India

    if tz_name:
        try:
            tz = timezone(tz_name)
            localized_dt = tz.localize(birth_datetime)
            offset_seconds = localized_dt.utcoffset().total_seconds()
            time_offset = round(offset_seconds / 3600, 2)
        except Exception as e:
            print(f"Could not compute timezone offset for {tz_name}: {e}")

    return time_offset


def to_julian_day(dt: datetime, tz_offset: float) -> float:
    dt_utc = dt - timedelta(hours=tz_offset)
    return swe.julday(
        dt_utc.year,
        dt_utc.month,
        dt_utc.day,
        dt_utc.hour + dt_utc.minute / 60 + dt_utc.second / 3600,
    )


def get_divisional_sign(original_degree: float, varga_division: int) -> str:
    sign_index = int((original_degree % 30) * varga_division // (30))
    final_sign = (int(original_degree // 30) * varga_division + sign_index) % 12
    return ZODIAC_SIGNS[final_sign]


def get_zodiac_sign(degree: float) -> str:
    return ZODIAC_SIGNS[int(degree // 30) % 12]


def sanitize_coordinates(lat, lon):
    return max(min(lat, 90), -90), max(min(lon, 180), -180)


def get_house_signs(asc_deg: float) -> List[str]:
    asc_index = int(asc_deg // 30) % 12
    return [ZODIAC_SIGNS[(asc_index + i) % 12] for i in range(12)]


def get_ascendant(jd: float, lat: float, lon: float) -> float:
    flags = swe.FLG_SIDEREAL | swe.FLG_SWIEPH
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    ascmc = swe.houses_ex(jd, lat, lon, b"A", flags)[0]
    return ascmc[0]  # Ascendant degree


def get_planet_positions(jd: float) -> Dict[str, Dict]:
    planet_data = {}
    swe.set_sid_mode(swe.SIDM_LAHIRI)

    for name, pid in PLANETS.items():
        if name == "Ketu":
            continue  # we'll calculate Ketu manually after Rahu
        pos, _ = swe.calc_ut(jd, pid, swe.FLG_SIDEREAL | swe.FLG_SPEED)
        lon = pos[0]
        speed = pos[3] if len(pos) > 3 else 0.0
        retrograde = speed < 0

        planet_data[name] = {
            "longitude": lon,
            "degree": lon % 30,
            "retrograde": retrograde,
            "speed": speed,
        }
        if name == "Rahu":
            rahu_lon = pos[0]
            # Save Rahu
            planet_data["Rahu"] = {
                "longitude": rahu_lon,
                "degree": rahu_lon % 30,
                "retrograde": True,
                "speed": pos[3],
            }

            # Now compute Ketu from Rahu
            ketu_lon = (rahu_lon + 180) % 360
            planet_data["Ketu"] = {
                "longitude": ketu_lon,
                "degree": ketu_lon % 30,
                "retrograde": True,
                "speed": -pos[3],
            }

    return planet_data


def is_combust(planet_name: str, planet_deg: float, sun_deg: float) -> bool:
    """
    Simple combustion logic:
    Mercury: < 12°, Venus: < 10°, Mars: < 17°, Jupiter: < 11°, Saturn: < 15°
    """
    diff = abs((planet_deg - sun_deg + 180) % 360 - 180)  # shortest angular distance
    combustion_ranges = {
        "Mercury": 12,
        "Venus": 10,
        "Mars": 17,
        "Jupiter": 11,
        "Saturn": 15,
    }
    return diff < combustion_ranges.get(planet_name, 8)  # default 8° for others
