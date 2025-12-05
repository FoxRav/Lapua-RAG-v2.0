#!/usr/bin/env python3
"""Quick test of Groq API."""
import os
from openai import OpenAI

client = OpenAI(
    api_key=os.environ.get("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
)

# Simple test
try:
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": "Say OK"}],
        max_tokens=10,
    )
    print(f"Test OK: {response.choices[0].message.content}")
except Exception as e:
    print(f"Error: {e}")

# Test with Finnish content
try:
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": "Vastaa JSON: {'testi': 'ok', 'arvo': 0.5}"}],
        max_tokens=50,
        temperature=0.1,
    )
    print(f"Finnish test: {response.choices[0].message.content}")
except Exception as e:
    print(f"Finnish error: {e}")

