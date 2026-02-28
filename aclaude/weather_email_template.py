#!/usr/bin/env python3
"""
Weather Email Report - HTML Template + Send via Microsoft Graph API
Shows current weather + 2-hour interval forecast from send time.
Usage: python weather_email_template.py [--test] [--city "Ρόδος"]
"""
import subprocess, json, sys, os, io, requests, urllib.request, urllib.parse
from datetime import datetime, timedelta

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

SKILL_PATH = r"C:\Users\Στέφανος\.claude\skills\weather-open-meteo\scripts\weather.py"

WEATHER_ICONS = {
    0: ("☀️", "Αίθριος", "#f39c12"),
    1: ("🌤️", "Κυρίως αίθριος", "#f1c40f"),
    2: ("⛅", "Μερικώς νεφελώδης", "#95a5a6"),
    3: ("☁️", "Συννεφιασμένος", "#7f8c8d"),
    45: ("🌫️", "Ομίχλη", "#bdc3c7"),
    48: ("🌫️", "Παγωμένη ομίχλη", "#bdc3c7"),
    51: ("🌦️", "Ελαφρύ ψιχάλισμα", "#3498db"),
    53: ("🌦️", "Μέτριο ψιχάλισμα", "#3498db"),
    55: ("🌧️", "Έντονο ψιχάλισμα", "#2980b9"),
    61: ("🌧️", "Ελαφριά βροχή", "#2980b9"),
    63: ("🌧️", "Μέτρια βροχή", "#2980b9"),
    65: ("🌧️", "Έντονη βροχή", "#2c3e50"),
    71: ("🌨️", "Ελαφρύ χιόνι", "#ecf0f1"),
    73: ("🌨️", "Μέτριο χιόνι", "#ecf0f1"),
    75: ("🌨️", "Έντονο χιόνι", "#bdc3c7"),
    80: ("🌦️", "Ελαφριά μπόρα", "#3498db"),
    81: ("🌧️", "Μέτρια μπόρα", "#2980b9"),
    82: ("⛈️", "Ισχυρή μπόρα", "#8e44ad"),
    95: ("⛈️", "Καταιγίδα", "#8e44ad"),
    96: ("⛈️", "Καταιγίδα με χαλάζι", "#8e44ad"),
    99: ("⛈️", "Ισχυρή καταιγίδα με χαλάζι", "#6c3483"),
}

WIND_DIRS_GR = {
    "N": "Β", "NNE": "ΒΒΑ", "NE": "ΒΑ", "ENE": "ΑΒΑ",
    "E": "Α", "ESE": "ΑΝΑ", "SE": "ΝΑ", "SSE": "ΝΝΑ",
    "S": "Ν", "SSW": "ΝΝΔ", "SW": "ΝΔ", "WSW": "ΔΝΔ",
    "W": "Δ", "WNW": "ΔΒΔ", "NW": "ΒΔ", "NNW": "ΒΒΔ"
}

DAYS_GR = {
    "Monday": "Δευτέρα", "Tuesday": "Τρίτη", "Wednesday": "Τετάρτη",
    "Thursday": "Πέμπτη", "Friday": "Παρασκευή", "Saturday": "Σάββατο", "Sunday": "Κυριακή"
}

MONTHS_GR = {
    1: "Ιαν", 2: "Φεβ", 3: "Μαρ", 4: "Απρ", 5: "Μάι", 6: "Ιούν",
    7: "Ιούλ", 8: "Αύγ", 9: "Σεπ", 10: "Οκτ", 11: "Νοέ", 12: "Δεκ"
}


def wind_direction(degrees):
    dirs = ["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"]
    idx = round(degrees / 22.5) % 16
    eng = dirs[idx]
    return WIND_DIRS_GR.get(eng, eng)


def geocode(city):
    """Get coordinates for a city."""
    params = urllib.parse.urlencode({"name": city, "count": 3, "language": "el", "format": "json"})
    url = f"https://geocoding-api.open-meteo.com/v1/search?{params}"
    with urllib.request.urlopen(url, timeout=10) as resp:
        data = json.loads(resp.read().decode())
    results = data.get("results", [])
    if not results:
        raise Exception(f"City not found: {city}")
    return results[0]


def get_weather_data(city="Ρόδος", forecast_days=2):
    """Fetch current + hourly + daily weather data directly from Open-Meteo API."""
    loc = geocode(city)
    lat, lon = loc["latitude"], loc["longitude"]

    params = urllib.parse.urlencode({
        "latitude": lat,
        "longitude": lon,
        "current": ",".join([
            "temperature_2m", "relative_humidity_2m", "apparent_temperature",
            "precipitation", "weather_code", "cloud_cover",
            "wind_speed_10m", "wind_direction_10m", "wind_gusts_10m",
            "surface_pressure"
        ]),
        "hourly": ",".join([
            "temperature_2m", "apparent_temperature", "precipitation_probability",
            "precipitation", "weather_code", "wind_speed_10m", "wind_direction_10m",
            "relative_humidity_2m"
        ]),
        "daily": ",".join([
            "weather_code", "temperature_2m_max", "temperature_2m_min",
            "apparent_temperature_max", "apparent_temperature_min",
            "precipitation_sum", "precipitation_probability_max",
            "wind_speed_10m_max", "wind_gusts_10m_max",
            "sunrise", "sunset", "uv_index_max"
        ]),
        "timezone": "auto",
        "forecast_days": min(forecast_days, 16),
        "wind_speed_unit": "kmh"
    })
    url = f"https://api.open-meteo.com/v1/forecast?{params}"

    with urllib.request.urlopen(url, timeout=15) as resp:
        data = json.loads(resp.read().decode())

    data["location"] = loc
    return data


def get_2hour_forecast(data):
    """Extract 2-hour interval forecast slots from current time onwards."""
    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    if not times:
        return []

    now = datetime.now()
    # Round to next even hour
    current_hour = now.hour
    if current_hour % 2 == 1:
        start_hour = current_hour + 1
    else:
        start_hour = current_hour + 2

    slots = []
    for i, t_str in enumerate(times):
        dt = datetime.strptime(t_str, "%Y-%m-%dT%H:%M")
        # Only future hours, every 2 hours
        if dt < now:
            continue
        if dt.hour % 2 != 0:
            continue

        wcode = hourly["weather_code"][i]
        icon, desc, _ = WEATHER_ICONS.get(wcode, ("🌡️", "Άγνωστο", "#95a5a6"))

        slots.append({
            "time": dt.strftime("%H:%M"),
            "date": dt,
            "temp": hourly["temperature_2m"][i],
            "feels": hourly["apparent_temperature"][i],
            "precip_prob": hourly.get("precipitation_probability", [0]*len(times))[i],
            "precip": hourly.get("precipitation", [0]*len(times))[i],
            "wind_speed": hourly["wind_speed_10m"][i],
            "wind_dir": wind_direction(hourly["wind_direction_10m"][i]),
            "humidity": hourly["relative_humidity_2m"][i],
            "wcode": wcode,
            "icon": icon,
            "desc": desc,
        })

        if len(slots) >= 12:  # Max 12 slots (24 hours ahead)
            break

    return slots


def build_html_email(data, city="Ρόδος"):
    now = datetime.now()
    day_name = DAYS_GR.get(now.strftime("%A"), now.strftime("%A"))
    month = MONTHS_GR.get(now.month, str(now.month))
    date_str = f"{day_name} {now.day} {month} {now.year}"
    time_str = now.strftime("%H:%M")

    cur = data["current"]
    temp = cur["temperature_2m"]
    feels = cur["apparent_temperature"]
    humidity = cur["relative_humidity_2m"]
    cloud = cur["cloud_cover"]
    wind_speed = cur["wind_speed_10m"]
    wind_dir = wind_direction(cur["wind_direction_10m"])
    wind_gusts = cur["wind_gusts_10m"]
    precip = cur["precipitation"]
    pressure = cur["surface_pressure"]
    wcode = cur["weather_code"]
    icon, desc, _ = WEATHER_ICONS.get(wcode, ("🌡️", "Άγνωστο", "#95a5a6"))

    loc = data["location"]
    location_name = f"{loc['name']}, {loc.get('admin1', '')}"

    daily = data.get("daily", {})
    temp_max = daily.get("temperature_2m_max", [None])[0]
    temp_min = daily.get("temperature_2m_min", [None])[0]
    uv_index = daily.get("uv_index_max", [None])[0]
    sunrise = daily.get("sunrise", [""])[0].split("T")[-1] if daily.get("sunrise") else ""
    sunset = daily.get("sunset", [""])[0].split("T")[-1] if daily.get("sunset") else ""
    precip_prob = daily.get("precipitation_probability_max", [0])[0]

    # UV level
    if uv_index and uv_index >= 8:
        uv_color, uv_label = "#e74c3c", "Πολύ Υψηλός"
    elif uv_index and uv_index >= 6:
        uv_color, uv_label = "#e67e22", "Υψηλός"
    elif uv_index and uv_index >= 3:
        uv_color, uv_label = "#f1c40f", "Μέτριος"
    else:
        uv_color, uv_label = "#27ae60", "Χαμηλός"

    # Temperature gradient
    if temp >= 30:
        bg_gradient = "linear-gradient(135deg, #e74c3c 0%, #f39c12 100%)"
    elif temp >= 20:
        bg_gradient = "linear-gradient(135deg, #f39c12 0%, #f1c40f 100%)"
    elif temp >= 10:
        bg_gradient = "linear-gradient(135deg, #3498db 0%, #2ecc71 100%)"
    else:
        bg_gradient = "linear-gradient(135deg, #2c3e50 0%, #3498db 100%)"

    # Build 2-hour forecast section
    forecast_slots = get_2hour_forecast(data)
    forecast_html = _build_forecast_rows(forecast_slots)

    html = f"""<!DOCTYPE html>
<html lang="el">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;font-family:'Segoe UI',Tahoma,Geneva,Verdana,sans-serif;background-color:#f0f4f8;">

<!-- Container -->
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color:#f0f4f8;">
<tr><td align="center" style="padding:20px 10px;">

<!-- Main Card -->
<table role="presentation" width="600" cellspacing="0" cellpadding="0" style="background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">

<!-- Header -->
<tr>
<td style="background:{bg_gradient};padding:32px 40px;text-align:center;">
  <div style="font-size:56px;margin-bottom:8px;">{icon}</div>
  <div style="color:white;font-size:42px;font-weight:700;letter-spacing:-1px;">{temp}&deg;C</div>
  <div style="color:rgba(255,255,255,0.85);font-size:16px;margin-top:4px;">{desc} &bull; Αισθητή {feels}&deg;C</div>
  <div style="color:rgba(255,255,255,0.7);font-size:14px;margin-top:12px;">
    &#128205; {location_name}
  </div>
  <div style="color:rgba(255,255,255,0.6);font-size:13px;margin-top:4px;">
    {date_str} &bull; {time_str}
  </div>
</td>
</tr>

<!-- Stats Grid -->
<tr>
<td style="padding:24px 30px 8px;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
  <tr>
    <td width="33%" style="text-align:center;padding:12px 8px;">
      <div style="font-size:24px;">&#127777;</div>
      <div style="color:#7f8c8d;font-size:11px;text-transform:uppercase;letter-spacing:1px;margin:4px 0;">Εύρος</div>
      <div style="color:#2c3e50;font-size:18px;font-weight:600;">{temp_min}&deg; / {temp_max}&deg;</div>
    </td>
    <td width="33%" style="text-align:center;padding:12px 8px;border-left:1px solid #ecf0f1;border-right:1px solid #ecf0f1;">
      <div style="font-size:24px;">&#128167;</div>
      <div style="color:#7f8c8d;font-size:11px;text-transform:uppercase;letter-spacing:1px;margin:4px 0;">Υγρασία</div>
      <div style="color:#2c3e50;font-size:18px;font-weight:600;">{humidity}%</div>
    </td>
    <td width="33%" style="text-align:center;padding:12px 8px;">
      <div style="font-size:24px;">&#128168;</div>
      <div style="color:#7f8c8d;font-size:11px;text-transform:uppercase;letter-spacing:1px;margin:4px 0;">Άνεμος</div>
      <div style="color:#2c3e50;font-size:18px;font-weight:600;">{wind_speed} km/h {wind_dir}</div>
    </td>
  </tr>
  </table>
</td>
</tr>

<!-- Divider -->
<tr><td style="padding:0 30px;"><hr style="border:none;border-top:1px solid #ecf0f1;margin:8px 0;"></td></tr>

<!-- Details Row -->
<tr>
<td style="padding:8px 30px 24px;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
  <tr>
    <td width="25%" style="text-align:center;padding:12px 4px;">
      <div style="font-size:20px;">&#128309;</div>
      <div style="color:#95a5a6;font-size:10px;margin:4px 0;">Πίεση</div>
      <div style="color:#34495e;font-size:14px;font-weight:600;">{pressure} hPa</div>
    </td>
    <td width="25%" style="text-align:center;padding:12px 4px;">
      <div style="font-size:20px;">&#9729;</div>
      <div style="color:#95a5a6;font-size:10px;margin:4px 0;">Νέφωση</div>
      <div style="color:#34495e;font-size:14px;font-weight:600;">{cloud}%</div>
    </td>
    <td width="25%" style="text-align:center;padding:12px 4px;">
      <div style="font-size:20px;">&#127783;</div>
      <div style="color:#95a5a6;font-size:10px;margin:4px 0;">Βροχή</div>
      <div style="color:#34495e;font-size:14px;font-weight:600;">{precip} mm ({precip_prob}%)</div>
    </td>
    <td width="25%" style="text-align:center;padding:12px 4px;">
      <div style="font-size:20px;">&#9728;</div>
      <div style="color:#95a5a6;font-size:10px;margin:4px 0;">UV Index</div>
      <div style="color:{uv_color};font-size:14px;font-weight:600;">{uv_index} ({uv_label})</div>
    </td>
  </tr>
  </table>
</td>
</tr>

<!-- Wind Gusts + Sunrise/Sunset -->
<tr>
<td style="padding:0 30px 24px;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f8f9fa;border-radius:12px;">
  <tr>
    <td width="33%" style="text-align:center;padding:16px 8px;">
      <div style="font-size:20px;">&#127788;</div>
      <div style="color:#95a5a6;font-size:10px;">Ριπές</div>
      <div style="color:#34495e;font-size:14px;font-weight:600;">{wind_gusts} km/h</div>
    </td>
    <td width="33%" style="text-align:center;padding:16px 8px;border-left:1px solid #e8e8e8;border-right:1px solid #e8e8e8;">
      <div style="font-size:20px;">&#127749;</div>
      <div style="color:#95a5a6;font-size:10px;">Ανατολή</div>
      <div style="color:#34495e;font-size:14px;font-weight:600;">{sunrise}</div>
    </td>
    <td width="33%" style="text-align:center;padding:16px 8px;">
      <div style="font-size:20px;">&#127751;</div>
      <div style="color:#95a5a6;font-size:10px;">Δύση</div>
      <div style="color:#34495e;font-size:14px;font-weight:600;">{sunset}</div>
    </td>
  </tr>
  </table>
</td>
</tr>

<!-- 2-HOUR FORECAST SECTION -->
<tr>
<td style="padding:0 30px 8px;">
  <div style="background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);border-radius:12px;padding:16px 20px;">
    <div style="color:white;font-size:16px;font-weight:700;margin-bottom:4px;">&#128336; Πρόβλεψη 24 ωρών ανά 2 ώρες</div>
    <div style="color:rgba(255,255,255,0.7);font-size:12px;">Επόμενες 24 ώρες από τώρα</div>
  </div>
</td>
</tr>

{forecast_html}

<!-- Footer -->
<tr>
<td style="background:#f8f9fa;padding:16px 30px;text-align:center;border-top:1px solid #ecf0f1;">
  <div style="color:#bdc3c7;font-size:11px;">
    &#129302; AgelClaw Weather &bull; &#128336; {time_str}
  </div>
</td>
</tr>

</table>
</td></tr>
</table>

</body>
</html>"""
    subject = f"{icon} Καιρός {loc['name']}: {temp}°C - {desc} | {date_str} {time_str}"
    return html, subject


def _build_forecast_rows(slots):
    """Build HTML rows for 2-hour forecast slots."""
    if not slots:
        return """<tr><td style="padding:8px 30px 24px;text-align:center;color:#95a5a6;font-size:13px;">
        Δεν υπάρχουν διαθέσιμα δεδομένα πρόβλεψης.
        </td></tr>"""

    rows_html = ""
    for i in range(0, len(slots), 4):
        chunk = slots[i:i+4]
        cells = ""
        for s in chunk:
            # Precipitation color
            if s["precip_prob"] >= 60:
                precip_color = "#e74c3c"
            elif s["precip_prob"] >= 30:
                precip_color = "#e67e22"
            else:
                precip_color = "#27ae60"

            cells += f"""
            <td width="{100//len(chunk)}%" style="text-align:center;padding:12px 6px;vertical-align:top;">
              <div style="color:#7f8c8d;font-size:13px;font-weight:600;">{s['time']}</div>
              <div style="font-size:28px;margin:6px 0;">{s['icon']}</div>
              <div style="color:#2c3e50;font-size:20px;font-weight:700;">{s['temp']}&deg;</div>
              <div style="color:#95a5a6;font-size:11px;margin-top:2px;">Αισθ. {s['feels']}&deg;</div>
              <div style="margin-top:6px;font-size:11px;color:{precip_color};font-weight:600;">&#127783; {s['precip_prob']}%</div>
              <div style="font-size:10px;color:#95a5a6;margin-top:2px;">&#128168; {s['wind_speed']} {s['wind_dir']}</div>
              <div style="font-size:10px;color:#95a5a6;">&#128167; {s['humidity']}%</div>
            </td>"""

        rows_html += f"""
<tr>
<td style="padding:4px 30px;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f8f9fa;border-radius:10px;">
  <tr>{cells}</tr>
  </table>
</td>
</tr>"""

    # Add spacing after forecast
    rows_html += """<tr><td style="padding:0 0 16px;"></td></tr>"""
    return rows_html


def send_email(to_list, subject, html_body):
    """Send email via Microsoft Graph API"""
    client_id = os.environ.get("OUTLOOK_CLIENT_ID")
    client_secret = os.environ.get("OUTLOOK_CLIENT_SECRET")
    tenant_id = os.environ.get("OUTLOOK_TENANT_ID")
    user_email = os.environ.get("OUTLOOK_USER_EMAIL", "sdrakos@agel.ai")

    # Get access token
    token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    token_data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": "https://graph.microsoft.com/.default",
        "grant_type": "client_credentials"
    }
    token_resp = requests.post(token_url, data=token_data)
    token_resp.raise_for_status()
    access_token = token_resp.json()["access_token"]

    # Build recipients
    recipients = [{"emailAddress": {"address": addr.strip()}} for addr in to_list if addr.strip()]

    # Send email
    send_url = f"https://graph.microsoft.com/v1.0/users/{user_email}/sendMail"
    email_payload = {
        "message": {
            "subject": subject,
            "body": {
                "contentType": "HTML",
                "content": html_body
            },
            "toRecipients": recipients
        },
        "saveToSentItems": True
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    resp = requests.post(send_url, json=email_payload, headers=headers)
    resp.raise_for_status()
    print(f"✅ Email sent to {', '.join(to_list)} (HTTP {resp.status_code})")
    return True


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Weather Email Report")
    parser.add_argument("--city", default="Ρόδος", help="City name")
    parser.add_argument("--days", type=int, default=2, help="Forecast days (1-16, default 2)")
    parser.add_argument("--test", action="store_true", help="Send test email to stefanos only")
    parser.add_argument("--to", nargs="+", default=["stefanos.drakos@gmail.com", "aggelikimastrodimitri@gmail.com", "chalikias@hotmail.com"],
                        help="Recipients")
    args = parser.parse_args()

    print(f"🌤️ Fetching weather for {args.city}...")
    data = get_weather_data(args.city, forecast_days=args.days)
    html, subject = build_html_email(data, args.city)

    if args.test:
        recipients = ["stefanos.drakos@gmail.com"]
        subject = f"[TEST] {subject}"
    else:
        recipients = args.to

    print(f"📧 Sending to: {', '.join(recipients)}")
    print(f"📋 Subject: {subject}")
    send_email(recipients, subject, html)
    print("🎉 Done!")
