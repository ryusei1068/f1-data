import os
import logging
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
import fastf1
from fastapi import FastAPI, Query, HTTPException
import pytz
from datetime import timedelta


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    fastf1.Cache.enable_cache("fastf1_cache")
    logger.info("FastF1 cache enabled.")
except Exception as e:
    logger.warning(f"Could not enable FastF1 cache: {e}")

app = FastAPI()
app.state.influx_client = None
app.state.bucket = None


def write_to_influx(points):
    write_api = app.state.influx_client.write_api(write_options=SYNCHRONOUS)
    if points:
        write_api.write(bucket=app.state.bucket, record=points)


def write_lap_data(session_info, laps_data):
    """Writes lap data to InfluxDB."""
    logger.info(f"Writing lap data for {len(laps_data)} laps...")
    points = []

    absolute_start = session_info["session_date"] + session_info["session_start_time"]
    if absolute_start.tzinfo is None:
        absolute_start = pytz.utc.localize(absolute_start)
    else:
        absolute_start = absolute_start.astimezone(pytz.utc)

    for _, lap in laps_data.iterrows():
        lap_timestamp = lap["LapStartDate"].tz_localize("UTC")
        p = (
            Point("lap_data")
            .tag("year", session_info["year"])
            .tag("race", session_info["race"])
            .tag("session", session_info["session_type"])
            .tag("driver_number", int(lap["DriverNumber"]))
            .tag("driver", lap["Driver"])
            .field("lap_number", int(lap["LapNumber"]))
            .field("position", lap["Position"])
            .time(lap_timestamp, WritePrecision.S)
        )

        lap_time_sec = lap["LapTime"].total_seconds()
        if lap_time_sec is not None:
            p.field("lap_time_sec", lap_time_sec)

        points.append(p)

    write_to_influx(points)
    logger.info("Finished writing lap data.")


def write_weather_data(session_info, weather_data):
    """Writes weather data to InfluxDB."""
    if weather_data.empty:
        logger.info("No weather data to write.")
        return
    logger.info(f"Writing weather data for {len(weather_data)} entries...")
    points = []

    absolute_start = session_info["session_date"] + session_info["session_start_time"]
    if absolute_start.tzinfo is None:
        absolute_start = pytz.utc.localize(absolute_start)
    else:
        absolute_start = absolute_start.astimezone(pytz.utc)

    for _, weather in weather_data.iterrows():
        timestamp = absolute_start + weather["Time"]

        p = (
            Point("weather")
            .tag("year", session_info["year"])
            .tag("race", session_info["race"])
            .tag("session", session_info["session_type"])
            .field("air_temp", float(weather["AirTemp"]))
            .field("humidity", float(weather["Humidity"]))
            .field("pressure", float(weather["Pressure"]))
            .field("rainfall", bool(weather["Rainfall"]))
            .field("track_temp", float(weather["TrackTemp"]))
            .field("wind_direction", int(weather["WindDirection"]))
            .field("wind_speed", float(weather["WindSpeed"]))
            .time(timestamp, WritePrecision.S)
        )
        points.append(p)

    write_to_influx(points)
    logger.info("Finished writing weather data.")


def write_race_control(session_info, messages):
    """Writes race control messages to InfluxDB."""
    if messages.empty:
        logger.info("No race control messages to write.")
        return
    logger.info(f"Writing race control messages for {len(messages)} entries...")
    points = []
    for _, msg in messages.iterrows():
        timestamp = msg["Time"].tz_localize("UTC")
        p = (
            Point("race_control")
            .tag("year", session_info["year"])
            .tag("race", session_info["race"])
            .tag("session", session_info["session_type"])
        )
        p.field("message", msg["Message"])
        p.time(timestamp, WritePrecision.S)
        points.append(p)

    write_to_influx(points)
    logger.info("Finished writing race control messages.")


@app.get("/history")
async def fetch_history(
    year: int = Query(...),
    race: str = Query(...),
    session_type: str = Query("R", description="Session type (FP1, FP2, FP3, Q, R)"),
):
    session_str = f"{year} {race} {session_type}"
    logger.info(f"Fetching historical data for: {session_str}")

    try:
        session = fastf1.get_session(year, race, session_type)
        session.load(weather=True, messages=True, laps=True)
        logger.info(f"Session data loaded for: {session_str}")

        ts = session.event.get_session_date(session.name).tz_convert("UTC")
        session_info = {
            "year": year,
            "race": race,
            "session_type": session.name,
            "session_start_time": timedelta(
                seconds=session.session_start_time.total_seconds()
            ),
            "session_date": ts,
        }

        write_lap_data(session_info, session.laps)
        write_weather_data(session_info, session.weather_data)
        write_race_control(session_info, session.race_control_messages)
        return {"status": f"Successfully fetched and saved data for {session_str}"}

    except fastf1.api.SessionNotAvailableError as e:
        logger.error(
            f"FastF1 API error - session data not available for {session_str}: {e}"
        )
        raise HTTPException(
            status_code=404,
            detail=f"Session data not available via FastF1 API for {session_str}. It might be too old or not processed yet. Error: {e}",
        )
    except ConnectionRefusedError:
        logger.error("InfluxDB connection refused")
        raise HTTPException(status_code=503, detail="Could not connect to InfluxDB")
    except Exception as e:
        logger.error(
            f"An unexpected error occurred for {session_str}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {e}"
        )


@app.on_event("startup")
async def startup_event():
    INFLUX_URL = os.getenv("INFLUXDB_URL", "http://localhost:8086")
    TOKEN = os.getenv("INFLUXDB_TOKEN")
    ORG = os.getenv("INFLUXDB_ORG")
    BUCKET = os.getenv("INFLUXDB_BUCKET")

    app.state.influx_client = InfluxDBClient(url=INFLUX_URL, token=TOKEN, org=ORG)
    app.state.bucket = BUCKET


@app.on_event("shutdown")
async def shutdown_event():
    app.state.influx_client.close()
