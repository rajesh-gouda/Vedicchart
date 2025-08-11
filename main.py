from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime
from fastapi.staticfiles import StaticFiles
from datetime import datetime
from utils import (
    detect_yogas,
    create_kundali_with_planets,
    SYSTEM_PROMPT,
    convert_datetime,
    create_kundali_with_transits,
    get_daily_horoscope,
    get_timezone_offset,
)
from vedic import (
    get_birth_chart,
    compare_transits,
    get_mahadasha,
    get_panchanga,
    get_divisional_chart,
    get_yogas,
)
import json
from openai import AsyncOpenAI
from typing import Any
import uuid
from dotenv import load_dotenv
import os
from logger import logger
from chat import router

load_dotenv()

app = FastAPI()
app.include_router(router)
templates = Jinja2Templates(directory="templates")

app.mount("/static", StaticFiles(directory="static"), name="static")

os.makedirs("static/birthcharts", exist_ok=True)

openai_client = AsyncOpenAI()


@app.get("/")
async def getdata(request: Request):
    return templates.TemplateResponse(
        "getdata.html",
        {
            "request": request,
            "chart_image": "/static/ganesha1.png",
        },
    )


@app.post("/getdata", response_class=HTMLResponse)
async def getdata_submit(
    request: Request,
    name: str = Form(...),
    gender: str = Form(...),
    dob: str = Form(...),
    tob: str = Form(...),
    place: str = Form(...),
    lat: float = Form(...),
    lon: float = Form(...),
):
    try:
        birth_datetime_str = f"{dob} {tob}:00"
        uuid4 = uuid.uuid4()
        time_offset = get_timezone_offset(lat, lon, birth_datetime_str)
        request_id = str(uuid4).replace("-", "")
        logger.info("Received Data:")
        logger.info(
            {
                "name": name,
                "gender": gender,
                "birth_datetime": birth_datetime_str,
                "place": place,
                "lat": lat,
                "lon": lon,
                "request_id": request_id,
            }
        )

        chart = get_birth_chart(birth_datetime_str, lat, lon, time_offset)
        logger.info(f"Generated Birth Chart for request ID {request_id}")
        # generate kundali image
        chart_name = f"static/birthcharts/kundali_{request_id}.png"

        # Get current transit
        transit_data = compare_transits(
            datetime.now(), lat, lon, chart["chart"], tz_offset=time_offset
        )
        logger.info(f"Generated Transit Data for request ID {request_id}")
        chart_name = create_kundali_with_transits(
            transit_data["transit_data"], filename=chart_name
        )
        if not chart_name:
            chart_name = "static/ganesha1.png"

        logger.info(f"Generated Kundali with transits for request ID {request_id}")
        # Format the transit data for the horoscope generation
        formatted_transit_text = transit_data["formatted_text"]

        # Format the birth chart for the horoscope generation
        formatted_birth_chart_text = chart["formatted_text"]
        # Call OpenAI to generate the horoscope
        horoscope = await get_daily_horoscope(
            birth_chart=formatted_birth_chart_text, transit_data=formatted_transit_text
        )
        if not horoscope:
            return templates.TemplateResponse(
                "error.html",
                {
                    "request": request,
                    "error": "Failed to generate horoscope. Please try again.",
                    "name": name,
                    "moon_sign": chart["chart"].planets["Moon"].sign,
                    "date": datetime.now().strftime("%B %d, %Y"),
                    "chart_image": chart_name,
                },
            )
        return templates.TemplateResponse(
            "result.html",
            {
                "request": request,
                "name": None if not name else name,
                "moon_sign": (
                    None
                    if not chart["chart"].planets.get("Moon")
                    else chart["chart"].planets["Moon"].sign
                ),
                "date": datetime.now().strftime("%B %d, %Y"),
                "chart_image": chart_name,
                "horoscope": horoscope,
            },
        )
    except Exception as e:
        logger.error(f"Error processing data: {e}")
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": "Failed to generate horoscope. Please try again.",
                "name": name,
                "moon_sign": None,
                "date": datetime.now().strftime("%B %d, %Y"),
                "chart_image": None if not chart_name else chart_name,
            },
        )
