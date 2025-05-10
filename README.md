# f1-data

This application fetches Formula 1 race data (laps, weather, race control messages) from the [FastF1](https://theoehrly.github.io/Fast-F1/) API, stores it in [InfluxDB](https://www.influxdata.com/), and enables visualization through [Grafana](https://grafana.com/).

## Features

- Fetch historical F1 data by year, race, and session
- Store data into InfluxDB
- Visualize data with Grafana dashboards
- Expose an API via FastAPI

---

## Requirements

You need the following software installed on your machine:

- [Docker](https://www.docker.com/) (recommended: version 20.x or later)
- [Docker Compose](https://docs.docker.com/compose/) (recommended: version 1.29 or later)

---

## How to Run

```bash
docker compose up
```

## Example: Fetching Data

You can fetch and store data for a specific year, race, and session using the /history API endpoint.

Example 1: 2024 British GP Race (R)
```
curl "http://localhost:8000/history?year=2024&race=Great+Britain&session_type=R"
```

Example 2: 2023 Monaco GP Qualifying (Q)

```
curl "http://localhost:8000/history?year=2023&race=Monaco&session_type=Q"
```

### Available session types:
| Session | Value |
|-- | -- |
| Free Practice 1 | FP1
| Free Practice 2 | FP2
| Free Practice 3 | FP3
| Qualifying | Q
| Sprint | S
| Race | R

(Default is "R")

# Lisence

This project is licensed under the MIT License, see the LICENSE file for details
