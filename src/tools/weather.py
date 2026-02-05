from pydantic import BaseModel, Field


class WeatherParams(BaseModel):
    city: str = Field(description="City name to get weather for")



async def get_weather(params: WeatherParams) -> str:
    """Get current weather for a city"""
    mock_weather = {
        "seattle": {"temp": "52°F", "condition": "Rainy", "humidity": "85%"},
        "new york": {"temp": "45°F", "condition": "Cloudy", "humidity": "60%"},
        "san francisco": {"temp": "58°F", "condition": "Foggy", "humidity": "75%"},
        "los angeles": {"temp": "72°F", "condition": "Sunny", "humidity": "40%"},
        "austin": {"temp": "78°F", "condition": "Sunny", "humidity": "55%"},
        "chicago": {"temp": "38°F", "condition": "Windy", "humidity": "65%"},
    }

    city_lower = params.city.lower()
    if city_lower in mock_weather:
        w = mock_weather[city_lower]
        return f"Weather in {params.city}: {w['temp']}, {w['condition']}, Humidity: {w['humidity']}"
    return f"Weather data not available for {params.city}"