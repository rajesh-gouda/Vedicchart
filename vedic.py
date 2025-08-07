from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple
from math import floor
import swisseph as swe
from vedicutils import (
    Chart,
    House,
    Planet,
    get_zodiac_sign,
    get_planet_positions,
    get_divisional_sign,
    sanitize_coordinates,
    to_julian_day,
    is_combust,
    get_ascendant,
    get_house_signs,
    ZODIAC_SIGNS,
    NAKSHATRA_SPAN,
    PLANETS,
    NAKSHATRA_TO_DASHA_LORD,
    DASHA_SEQUENCE,
    TITHIS,
    KARANAS,
    YOGAS,
    VARGA_DIVISIONS,
    NAKSHATRAS,
)

swe.set_ephe_path("./ephe")


def compare_transits(
    current_dt: datetime,
    lat: float,
    lon: float,
    natal_chart: Chart,
    tz_offset: float = 0.0,
) -> Dict[str, Any]:
    """
    Compares transit planets to natal chart houses/signs and returns insights.
    Returns both raw data and a formatted natural language text.
    """
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    jd = swe.julday(
        current_dt.year,
        current_dt.month,
        current_dt.day,
        current_dt.hour + current_dt.minute / 60 + current_dt.second / 3600 - tz_offset,
    )

    transits = get_planet_positions(jd)
    results = {}
    formatted_text = ""

    sun_deg = transits["Sun"]["longitude"]

    for planet, data in transits.items():
        sign = get_zodiac_sign(data["longitude"])

        # Determine natal house
        house_num = next((h.number for h in natal_chart.houses if h.sign == sign), None)

        # Check combustion
        combust = is_combust(planet, data["longitude"], sun_deg)

        # Build result entry
        results[planet] = {
            "transit_sign": sign,
            "transit_house": house_num,
            "retrograde": data["retrograde"],
            "combust": combust,
            "transit_longitude": data["longitude"],
        }

        # Format text
        formatted_text += (
            f"{planet} is in {sign} in your "
            f"{house_num}th house at {round(data['longitude'], 2)}°.\n"
        )

    return {
        "transit_data": results,
        "formatted_text": formatted_text.strip(),
    }


def get_birth_chart(
    birth_datetime_str: str, lat: float, lon: float, tz_offset: float
) -> Dict:
    from datetime import datetime

    # Prepare datetime object
    dt = datetime.strptime(birth_datetime_str, "%Y-%m-%d %H:%M:%S")
    jd = to_julian_day(dt, tz_offset)

    # Get Ascendant & Planet Data
    asc_deg = get_ascendant(jd, lat, lon)
    asc_sign = get_zodiac_sign(asc_deg)
    planet_positions = get_planet_positions(jd)
    house_signs = get_house_signs(asc_deg)

    # Initialize formatted text
    text = f"The Ascendant (Lagna) is in {asc_sign} sign.\n"

    # Build Houses
    houses = []
    for i, sign in enumerate(house_signs):
        houses.append(House(number=i + 1, sign=sign))

    # Assign planets to houses
    planets_by_name = {}
    for name, data in planet_positions.items():
        sign = get_zodiac_sign(data["longitude"])
        for house in houses:
            if house.sign == sign:
                house.planets.append(name)
                text += (
                    f"{name} is in your {house.number}th house in {house.sign} sign.\n"
                )
                break
        planets_by_name[name] = Planet(
            name=name,
            longitude=data["longitude"],
            sign=sign,
            retrograde=data["retrograde"],
        )

    chart = Chart(
        ascendant_sign=asc_sign,
        ascendant_degree=asc_deg,
        houses=houses,
        planets=planets_by_name,
    )

    return {"chart": chart, "formatted_text": text.strip()}


def get_mahadasha(chart, birth_datetime: datetime) -> Dict[str, Any]:
    moon_longitude = chart.planets["Moon"].longitude
    reference_date = datetime.now()

    # Determine birth nakshatra and lord
    nakshatra_index = floor(moon_longitude / NAKSHATRA_SPAN)
    nakshatra_lord = NAKSHATRA_TO_DASHA_LORD[nakshatra_index]
    lord_duration = dict(DASHA_SEQUENCE)[nakshatra_lord]

    # Determine how much time is left in the first dasha
    degree_within_nakshatra = moon_longitude % NAKSHATRA_SPAN
    portion_remaining = (NAKSHATRA_SPAN - degree_within_nakshatra) / NAKSHATRA_SPAN
    first_dasha_remaining_years = portion_remaining * lord_duration

    # Build the Dasha timeline
    all_dashas = []
    start = birth_datetime
    current_mahadasha = None
    mahadasha_found = False

    for i in range(50):  # enough to cover multiple cycles
        planet, duration_years = DASHA_SEQUENCE[i % len(DASHA_SEQUENCE)]

        # Adjust for first dasha only
        actual_years = duration_years
        if not mahadasha_found:
            if planet == nakshatra_lord:
                actual_years = first_dasha_remaining_years
                mahadasha_found = True
            else:
                continue  # Skip dasha until we reach starting one

        end = start + timedelta(days=actual_years * 365.25)

        dasha = {
            "lord": planet,
            "start": start,
            "end": end,
            "duration_years": duration_years,
        }

        if start <= reference_date <= end:
            current_mahadasha = {
                "planet": planet,
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "duration_years": duration_years,
            }

        all_dashas.append(dasha)
        start = end

    return {
        "reference_date": reference_date.isoformat(),
        "current_mahadasha": current_mahadasha,
        "all_dashas": all_dashas,
    }


def get_panchanga(dt: datetime, tz_offset: float = 0.0):
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    jd = swe.julday(
        dt.year,
        dt.month,
        dt.day,
        dt.hour + dt.minute / 60 + dt.second / 3600 - tz_offset,
    )

    # Sun and Moon
    moon_pos = swe.calc_ut(jd, swe.MOON, swe.FLG_SIDEREAL)[0][0]
    sun_pos = swe.calc_ut(jd, swe.SUN, swe.FLG_SIDEREAL)[0][0]
    moon_long = swe.calc_ut(jd, swe.MOON)[0][0]  # tropical for info
    sun_long = swe.calc_ut(jd, swe.SUN)[0][0]

    # Tithi (Moon-Sun angle)
    tithi_angle = (moon_pos - sun_pos) % 360
    tithi_index = floor(tithi_angle / 12)
    tithi = TITHIS[tithi_index]

    # Nakshatra & Pada
    nak_index = floor(moon_pos / (13 + 1 / 3))
    nakshatra = NAKSHATRAS[nak_index]
    pada = floor((moon_pos % (13 + 1 / 3)) / ((13 + 1 / 3) / 4)) + 1

    # Karana
    karana_index = floor(tithi_angle / 6) % len(KARANAS)
    karana = KARANAS[karana_index]

    # Yoga
    total_long = (sun_pos + moon_pos) % 360
    yoga_index = floor(total_long / (13 + 1 / 3))
    yoga = YOGAS[yoga_index]

    # Weekday
    weekday = dt.strftime("%A")

    return {
        "tithi": tithi,
        "vara": weekday,
        "yoga": yoga,
        "karana": karana,
        "nakshatra": nakshatra,
        "nakshatra_pada": pada,
        "moon_longitude": moon_long,
        "sun_longitude": sun_long,
        "moon_sidereal_longitude": moon_pos,
        "julian_day": jd,
    }


def get_divisional_chart(
    chart_type: str, dt: datetime, lat: float, lon: float, tz_offset: float = 0.0
) -> Dict:
    SUPPORTED_DIVISIONAL_CHARTS = {
        "D1": 1,  # Rashi (main chart)
        "D2": 2,  # Hora (wealth)
        "D3": 3,  # Drekkana (siblings, courage)
        "D4": 4,  # Chaturthamsha (fortune, property)
        "D5": 5,  # Panchamsha
        "D6": 6,  # Shashtamsha
        "D7": 7,  # Saptamsha (children)
        "D8": 8,  # Ashtamsha
        "D9": 9,  # Navamsha (marriage, dharma)
        "D10": 10,  # Dashamsha (career, karma)
        "D11": 11,  # Rudramsha (gains, power)
        "D12": 12,  # Dwadashamsha (parents)
        "D16": 16,  # Shodashamsha (vehicles, happiness)
        "D20": 20,  # Vimshamsha (spiritual progress)
        "D24": 24,  # Chaturvimshamsha (education, knowledge)
        "D27": 27,  # Bhamsha (strength, weaknesses)
        "D30": 30,  # Trimshamsha (evils, misfortunes)
        "D40": 40,  # Khavedamsha (maternal karma)
        "D45": 45,  # Akshavedamsha (paternal karma)
        "D60": 60,  # Shashtiamsha (past life, karma)
    }

    if chart_type not in SUPPORTED_DIVISIONAL_CHARTS:
        return {
            "chart": None,
            "formatted_text": "Unsupported divisional chart type. Please choose from: "
            + ", ".join(SUPPORTED_DIVISIONAL_CHARTS.keys()),
        }

    division_factor = SUPPORTED_DIVISIONAL_CHARTS[chart_type]

    # Prepare input
    lat, lon = sanitize_coordinates(lat, lon)
    jd = to_julian_day(dt, tz_offset)

    # Set sidereal mode for Lahiri ayanamsa
    swe.set_sid_mode(swe.SIDM_LAHIRI)

    # Get Ascendant degree
    ascmc = swe.houses_ex(jd, lat, lon, b"A", swe.FLG_SIDEREAL | swe.FLG_SWIEPH)[0]
    asc_deg = ascmc[0]
    asc_sign = get_divisional_sign(asc_deg, division_factor)

    # Get planetary positions
    planet_positions = get_planet_positions(jd)
    planets = {}
    house_objs = [
        House(
            number=i + 1,
            sign=ZODIAC_SIGNS[(ZODIAC_SIGNS.index(asc_sign) + i) % 12],
            planets=[],
        )
        for i in range(12)
    ]

    # Assign planets to divisional signs
    for pname, pdata in planet_positions.items():
        lon = pdata["longitude"]
        retro = pdata["retrograde"]
        d_sign = get_divisional_sign(lon, division_factor)

        planet = Planet(name=pname, longitude=lon, sign=d_sign, retrograde=retro)
        planets[pname] = planet

        for house in house_objs:
            if house.sign == d_sign:
                house.planets.append(pname)
                break

    # Construct chart object
    chart = Chart(
        ascendant_sign=asc_sign,
        ascendant_degree=asc_deg,
        houses=house_objs,
        planets=planets,
        chart_type=chart_type,
    )

    # Format for LLM
    text = f"The Ascendant (Lagna) is in {asc_sign} sign.\n"
    for house in house_objs:
        if house.planets:
            for p in house.planets:
                text += f"{p} is in your {house.number}th house in {house.sign} sign.\n"

    return {"chart": chart, "formatted_text": text.strip()}


def get_yogas(chart: Chart) -> List[str]:
    yogas = []
    p = chart.planets

    # 1. Raj Yoga: Kendra + Trikona lords together (e.g., 4th + 9th house lords conjunct)
    if "Jupiter" in p and "Moon" in p:
        if p["Jupiter"].sign == p["Moon"].sign:
            yogas.append("Gaja-Kesari Yoga (Jupiter and Moon in same sign)")

    # 2. Budh-Aditya Yoga: Sun and Mercury in same sign
    if "Sun" in p and "Mercury" in p:
        if p["Sun"].sign == p["Mercury"].sign:
            yogas.append("Budh-Aditya Yoga (Sun and Mercury in same sign)")

    # 3. Chandra-Mangal Yoga: Moon and Mars together
    if "Moon" in p and "Mars" in p:
        if p["Moon"].sign == p["Mars"].sign:
            yogas.append("Chandra-Mangal Yoga (Moon and Mars in same sign)")

    # 4. Neecha Bhanga Raja Yoga: A debilitated planet is cancelled by other rules (simplified)
    debilitated_planets = {
        "Sun": "Libra",
        "Moon": "Scorpio",
        "Mars": "Cancer",
        "Mercury": "Pisces",
        "Jupiter": "Capricorn",
        "Venus": "Virgo",
        "Saturn": "Aries",
    }
    exalted_planets = {
        "Sun": "Aries",
        "Moon": "Taurus",
        "Mars": "Capricorn",
        "Mercury": "Virgo",
        "Jupiter": "Cancer",
        "Venus": "Pisces",
        "Saturn": "Libra",
    }
    for planet, deb_sign in debilitated_planets.items():
        if planet in p and p[planet].sign == deb_sign:
            # Check if any other planet is in its exaltation sign in same house (simplified rule)
            for other, ex_sign in exalted_planets.items():
                if (
                    other in p
                    and p[other].sign == ex_sign
                    and p[other].sign == p[planet].sign
                ):
                    yogas.append(f"Neecha Bhanga Raja Yoga due to {planet} and {other}")
                    break

    return yogas


# Basic Ashtakavarga Calculation (simplified: only for Moon bindus for now)


def get_ashtakavarga_bindus(chart: Chart) -> Dict[str, int]:
    # Assign bindu values manually for Moon from classical scheme
    # This is simplified and *not* fully accurate

    # Bindu count for Moon in different signs (classical:
    # these values are just symbolic for prototype usage)
    MOON_BINDUS_BY_SIGN = {
        "Aries": 5,
        "Taurus": 8,
        "Gemini": 5,
        "Cancer": 6,
        "Leo": 5,
        "Virgo": 6,
        "Libra": 5,
        "Scorpio": 3,
        "Sagittarius": 4,
        "Capricorn": 3,
        "Aquarius": 4,
        "Pisces": 6,
    }
    moon_sign = chart.planets["Moon"].sign
    return {"Moon": MOON_BINDUS_BY_SIGN.get(moon_sign, 0)}
