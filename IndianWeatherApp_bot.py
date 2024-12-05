import os
import telebot
import requests
from datetime import datetime
from telebot import types

# Initialize bot with your token
BOT_TOKEN = "YOUR TELEGRAM BOT TOKEN HERE"  # Replace with your actual bot token
bot = telebot.TeleBot(BOT_TOKEN)

# OpenWeather API configuration
API_KEY = "OpenWeather API Key"  # PASTE YOUR OPENWEATHERAPP API KEY HERE
BASE_URL = "http://api.openweathermap.org/data/2.5/forecast"
CURRENT_URL = "http://api.openweathermap.org/data/2.5/weather"
AQI_URL = "http://api.openweathermap.org/data/2.5/air_pollution"

# Store user states
user_states = {}

def get_air_quality(lat, lon):
    params = {
        "lat": lat,
        "lon": lon,
        "appid": API_KEY
    }

    try:
        response = requests.get(AQI_URL, params=params)
        response.raise_for_status()
        aqi_data = response.json()
        return aqi_data['list'][0]['main']['aqi']  # Returns AQI value (1-5)
    except requests.exceptions.RequestException as e:
        return "Error fetching AQI data"

def get_aqi_description(aqi):
    if isinstance(aqi, str):
        return aqi
    aqi_levels = {
        1: "Good",
        2: "Fair",
        3: "Moderate",
        4: "Poor",
        5: "Very Poor"
    }
    return aqi_levels.get(aqi, "Unknown")

def get_current_weather(city):
    params = {
        "q": city,
        "appid": API_KEY,
        "units": "metric"
    }

    try:
        response = requests.get(CURRENT_URL, params=params)
        response.raise_for_status()
        weather_data = response.json()
        lat = weather_data['coord']['lat']
        lon = weather_data['coord']['lon']
        aqi = get_air_quality(lat, lon)
        return {
            'temp': weather_data['main']['temp'],
            'description': weather_data['weather'][0]['description'],
            'humidity': weather_data['main']['humidity'],
            'wind_speed': weather_data['wind']['speed'],
            'aqi': aqi,
            'aqi_description': get_aqi_description(aqi)
        }
    except requests.exceptions.RequestException as e:
        return f"Error fetching current weather: {e}"

def get_weather_forecast(city):
    params = {
        "q": city,
        "appid": API_KEY,
        "units": "metric",
        "cnt": 40  # Get 5 days of forecast data
    }

    try:
        response = requests.get(BASE_URL, params=params)
        response.raise_for_status()
        weather_data = response.json()

        # Get AQI data
        lat = weather_data['city']['coord']['lat']
        lon = weather_data['city']['coord']['lon']
        aqi = get_air_quality(lat, lon)

        forecast_data = process_weather_data(weather_data)
        return forecast_data, aqi
    except requests.exceptions.RequestException as e:
        return f"Error fetching weather data: {e}"

def process_weather_data(data):
    forecast = {}
    for item in data['list']:
        date = datetime.fromtimestamp(item['dt']).strftime('%Y-%m-%d')
        if date not in forecast:
            forecast[date] = {
                'date': date,
                'max_temp': item['main']['temp_max'],
                'min_temp': item['main']['temp_min'],
                'description': item['weather'][0]['description']
            }
        else:
            forecast[date]['max_temp'] = max(forecast[date]['max_temp'], item['main']['temp_max'])
            forecast[date]['min_temp'] = min(forecast[date]['min_temp'], item['main']['temp_min'])

    return sorted(forecast.values(), key=lambda x: x['date'])

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "Welcome to the Weather Forecast Bot!\nPlease enter a city name to get started.")
    user_states[message.chat.id] = {'step': 'waiting_for_city'}

def create_options_keyboard():
    keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    buttons = [
        types.KeyboardButton("Current Weather"),
        types.KeyboardButton("5 Days Forecast"),
        types.KeyboardButton("Air Quality Index")
    ]
    keyboard.add(*buttons)
    return keyboard

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    chat_id = message.chat.id

    if chat_id not in user_states:
        user_states[chat_id] = {'step': 'waiting_for_city'}

    if user_states[chat_id]['step'] == 'waiting_for_city':
        user_states[chat_id]['city'] = message.text
        user_states[chat_id]['step'] = 'waiting_for_option'
        bot.reply_to(message, "Please select an option:", reply_markup=create_options_keyboard())

    elif user_states[chat_id]['step'] == 'waiting_for_option':
        city = user_states[chat_id]['city']

        if message.text == "Current Weather":
            weather = get_current_weather(city)
            if isinstance(weather, str):
                bot.reply_to(message, weather)
            else:
                response = f"Current Weather in {city}:\n"
                response += f"Temperature: {weather['temp']:.1f}°C\n"
                response += f"Conditions: {weather['description']}\n"
                response += f"Humidity: {weather['humidity']}%\n"
                response += f"Wind Speed: {weather['wind_speed']} m/s\n"
                response += f"Air Quality Index: {weather['aqi']} ({weather['aqi_description']})"
                bot.reply_to(message, response)

        elif message.text == "5 Days Forecast":
            result = get_weather_forecast(city)
            if isinstance(result, str):
                bot.reply_to(message, result)
            else:
                forecast, aqi = result
                response = f"5-Day Weather Forecast for {city}:\n"
                response += f"Current Air Quality Index: {aqi} ({get_aqi_description(aqi)})\n\n"
                for day in forecast:
                    response += f"Date: {day['date']}\n"
                    response += f"Max Temperature: {day['max_temp']:.1f}°C\n"
                    response += f"Min Temperature: {day['min_temp']:.1f}°C\n"
                    response += f"Weather: {day['description']}\n\n"
                bot.reply_to(message, response)

        elif message.text == "Air Quality Index":
            try:
                # Get coordinates first
                response = requests.get(CURRENT_URL, params={"q": city, "appid": API_KEY})
                weather_data = response.json()
                lat = weather_data['coord']['lat']
                lon = weather_data['coord']['lon']
                aqi = get_air_quality(lat, lon)
                response = f"Air Quality in {city}:\n"
                response += f"AQI Value: {aqi}\n"
                response += f"Status: {get_aqi_description(aqi)}"
                bot.reply_to(message, response)
            except Exception as e:
                bot.reply_to(message, f"Error fetching AQI data: {e}")

        user_states[chat_id]['step'] = 'waiting_for_city'
        bot.reply_to(message, "Enter another city name to continue or use the same city to check other options.")

# Start the bot
bot.polling()
