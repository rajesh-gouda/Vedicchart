from typing import List
from core_astrology_engine.models.chart import Chart
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
from dotenv import load_dotenv
from openai import AsyncOpenAI
import json
from logger import logger
from timezonefinder import TimezoneFinder
from pytz import timezone, utc

load_dotenv()
openai_client = AsyncOpenAI()

SYSTEM_PROMPT = """
You are a Vedic astrologer. Based on the provided Vedic birth chart and current transit data, generate today's fortune strictly in JSON format. 

Output must be under 200 words in total and follow this exact format:

{
"Career_&_Studies": "",
"Finances": "",
"Health": "",
"Love_&_Family": ""
}

Each field should contain a short, insightful sentence (max 2 sentences) summarizing today's fortune based on Vedic astrology. Avoid unnecessary elaboration. Do not add explanations, labels, or headings outside the JSON format.
"""


def get_timezone_offset(lat: float, lon: float, birth_datetime_str: str) -> float:
    """Get the timezone offset in hours for the given latitude and longitude.
    Uses TimezoneFinder to determine the timezone and pytz to get the offset.
    """
    birth_datetime = datetime.fromisoformat(birth_datetime_str)
    # Get timezone from lat/lon
    tf = TimezoneFinder()
    tz_name = tf.timezone_at(lng=lon, lat=lat)

    # Default offset (e.g., for India if tz not found)
    time_offset = 5.5

    if tz_name:
        try:
            tz = timezone(tz_name)
            localized_dt = tz.localize(birth_datetime)
            offset_seconds = localized_dt.utcoffset().total_seconds()
            time_offset = round(offset_seconds / 3600, 2)
        except Exception as e:
            logger.warning(f"Could not compute timezone offset for {tz_name}: {e}")
    return time_offset


def convert_datetime(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")


def detect_yogas(chart: Chart) -> List[str]:
    yogas = []

    planet_signs = {planet.name: planet.sign for planet in chart.planets.values()}
    planet_houses = {}
    for house in chart.houses:
        for planet in house.planets:
            planet_houses[planet] = house.number

    # Gajakesari Yoga: Jupiter in kendra from Moon
    if "Jupiter" in planet_houses and "Moon" in planet_houses:
        moon_house = planet_houses["Moon"]
        jupiter_house = planet_houses["Jupiter"]
        if abs(jupiter_house - moon_house) in [0, 3, 6, 9]:
            yogas.append("Gajakesari Yoga")

    # Budhaditya Yoga: Sun and Mercury in same house
    if "Sun" in planet_houses and "Mercury" in planet_houses:
        if planet_houses["Sun"] == planet_houses["Mercury"]:
            yogas.append("Budhaditya Yoga")

    # Raj Yoga (simplified): Kendra-Trikona lords in same house
    kendra_houses = [1, 4, 7, 10]
    trikona_houses = [1, 5, 9]
    for p1, h1 in planet_houses.items():
        if h1 in kendra_houses:
            for p2, h2 in planet_houses.items():
                if p2 != p1 and h2 == h1 and h2 in trikona_houses:
                    yogas.append("Raj Yoga")
                    break

    # Neechabhanga Raja Yoga (Mercury in Pisces with Venus/Jupiter)
    if planet_signs.get("Mercury") == "Pisces":
        if (
            planet_signs.get("Venus") == "Pisces"
            or planet_signs.get("Jupiter") == "Pisces"
        ):
            yogas.append("Neechabhanga Raja Yoga (Mercury)")

    # Chandra-Mangal Yoga: Moon and Mars conjunction
    if "Moon" in planet_houses and "Mars" in planet_houses:
        if planet_houses["Moon"] == planet_houses["Mars"]:
            yogas.append("Chandra-Mangal Yoga")

    return yogas


def create_kundali_with_planets(
    birth_chart_data,
    base_image_path="static/kundali_with_numbers.png",
    filename="kundali_with_planets.png",
):
    """
    Generates a North Indian style Vedic birth chart with planets positioned
    according to the birth chart data, using a base image with house numbers.
    """

    # Load the base image with house numbers
    try:
        image = Image.open(base_image_path)
        size = image.size[0]  # Assuming square image
    except IOError:
        logger.error(f"Error: Could not load base image '{base_image_path}'")
        return None

    draw = ImageDraw.Draw(image)

    # Load fonts
    try:
        planet_font_size = int(size * 0.025)  # Font for planets
        planet_font = ImageFont.truetype("arial.ttf", planet_font_size)
    except IOError:
        planet_font = ImageFont.load_default()

    # House positions (shifted right to avoid overlapping with numbers)
    house_positions = {
        1: (315, 155),
        2: (160, 48),
        3: (54, 155),
        4: (155, 306),
        5: (39, 433),
        6: (167, 535),
        7: (318, 460),
        8: (451, 558),
        9: (566, 457),
        10: (470, 343),
        11: (576, 138),
        12: (463, 41),
    }

    # Planet abbreviations for compact display
    planet_abbreviations = {
        "Sun": "Su",
        "Moon": "Mo",
        "Mars": "Ma",
        "Mercury": "Me",
        "Jupiter": "Ju",
        "Venus": "Ve",
        "Saturn": "Sa",
        "Rahu": "Ra",
        "Ketu": "Ke",
    }

    # Draw planets in each house
    for house_data in birth_chart_data["houses"]:
        house_num = house_data["number"]
        planets = house_data["planets"]

        if house_num in house_positions and planets:
            house_x, house_y = house_positions[house_num]

            # Create abbreviated planet list
            planet_abbrevs = [
                planet_abbreviations.get(planet, planet[:2]) for planet in planets
            ]

            # Draw planets vertically
            total_planets = len(planet_abbrevs)
            line_height = 15  # Space between each planet initial

            # Calculate starting Y position to center the planets vertically
            start_y = house_y - ((total_planets - 1) * line_height / 2)

            for i, planet_abbrev in enumerate(planet_abbrevs):
                y_position = start_y + (i * line_height)
                draw.text(
                    (house_x, y_position),
                    planet_abbrev,
                    fill="#654321",
                    font=planet_font,
                    anchor="mm",
                )

    # Save the image
    image.save(filename)
    logger.info(f"Kundali with planets saved as '{filename}'")
    return image


def create_kundali_with_transits(
    transit_data,
    base_image_path="static/kundali_with_numbers.png",
    filename="kundali_with_transits.png",
):
    """
    Generates a North Indian style Vedic birth chart with planets positioned
    according to the transit (gochar) data, using a base image with house numbers.
    """

    # Load the base image with house numbers
    try:
        image = Image.open(base_image_path)
        size = image.size[0]  # Assuming square image
    except IOError:
        logger.error(f"Error: Could not load base image '{base_image_path}'")
        return None

    draw = ImageDraw.Draw(image)

    # Load fonts
    try:
        planet_font_size = int(size * 0.025)
        try:
            # Try system-specific arial.ttf first
            planet_font = ImageFont.truetype("arial.ttf", planet_font_size)
        except IOError:
            # Fallback to DejaVu
            planet_font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", planet_font_size
            )
    except IOError:
        # Fallback to default bitmap font
        planet_font = ImageFont.load_default()

    # House positions (shifted right to avoid overlapping with numbers)
    house_positions = {
        1: (315, 155),
        2: (160, 48),
        3: (54, 155),
        4: (155, 306),
        5: (39, 433),
        6: (167, 535),
        7: (318, 460),
        8: (451, 558),
        9: (566, 457),
        10: (470, 343),
        11: (576, 138),
        12: (463, 41),
    }

    # Planet abbreviations for compact display
    planet_abbreviations = {
        "Sun": "Su",
        "Moon": "Mo",
        "Mars": "Ma",
        "Mercury": "Me",
        "Jupiter": "Ju",
        "Venus": "Ve",
        "Saturn": "Sa",
        "Rahu": "Ra",
        "Ketu": "Ke",
    }

    # Group planets by house from transit data
    houses_with_planets = {}
    for planet_name, planet_info in transit_data.items():
        house_num = planet_info["transit_house"]

        if house_num not in houses_with_planets:
            houses_with_planets[house_num] = []

        # Get planet abbreviation
        planet_abbrev = planet_abbreviations.get(planet_name, planet_name[:2])

        # Add indicators for retrograde and combust planets
        # if planet_info.get("retrograde", False):
        #     planet_abbrev += "R"
        # if planet_info.get("combust", False):
        #     planet_abbrev += "C"

        houses_with_planets[house_num].append(planet_abbrev)

    # Draw planets in each house
    for house_num, planets in houses_with_planets.items():
        if house_num in house_positions and planets:
            house_x, house_y = house_positions[house_num]

            # Draw planets vertically
            total_planets = len(planets)
            line_height = 15  # Space between each planet initial

            # Calculate starting Y position to center the planets vertically
            start_y = house_y - ((total_planets - 1) * line_height / 2)

            for i, planet_abbrev in enumerate(planets):
                y_position = start_y + (i * line_height)

                # Use different colors for retrograde and combust planets
                color = "#654321"  # Default brown color
                # if "R" in planet_abbrev:
                #     color = "#8B0000"  # Dark red for retrograde
                # elif "C" in planet_abbrev:
                #     color = "#FF4500"  # Orange red for combust

                draw.text(
                    (house_x, y_position),
                    planet_abbrev,
                    fill=color,
                    font=planet_font,
                    anchor="mm",
                )

    # Save the image
    image.save(filename)
    logger.info(f"Kundali with transit planets saved as '{filename}'")
    return filename


async def get_daily_horoscope(birth_chart: str, transit_data: str) -> str:
    try:
        user_prompt = f"""
        Birth Chart:
        {birth_chart}

        Transit Data:
        {transit_data}
        """
        response = await openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.8,
            max_tokens=800,
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        logger.error(f"Error generating horoscope: {e}")
        return None
