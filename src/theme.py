"""CSS themes for CounterPro Streamlit app."""

DARK = """
<style>
html, body, [class*="css"]  {
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", sans-serif;
    background-color: #1c1c1e;
    color: #f2f2f7;
}

/* Input controls */
div[data-baseweb="select"] > div,
input[type="number"] {
    background-color: #2c2c2e;
    border: 1px solid #3a3a3c;
    border-radius: 12px;
    color: #f2f2f7;
}

/* Buttons */
.stButton>button {
    background-color: #0a84ff;
    color: white;
    border: none;
    border-radius: 12px;
    padding: 8px 16px;
    font-size: 0.9rem;
}

/* Slider accent */
div[data-baseweb="slider"] [role="slider"] {
    background-color: #0a84ff;
}

/* Smaller label fonts */
.stLabel, label { font-size: 0.85rem; }
h1 { font-size: 2rem; }
h2 { font-size: 1.5rem; }
</style>
"""

LIGHT = """
<style>
html, body, [class*="css"]  {
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", sans-serif;
    background-color: #ffffff;
    color: #1c1c1e;
}

/* Input controls */
div[data-baseweb="select"] > div,
input[type="number"] {
    background-color: #ffffff;
    border: 1px solid #d0d0d0;
    border-radius: 12px;
    color: #1c1c1e;
}

/* Buttons */
.stButton>button {
    background-color: #0a84ff;
    color: white;
    border: none;
    border-radius: 12px;
    padding: 8px 16px;
    font-size: 0.9rem;
}

/* Slider accent */
div[data-baseweb="slider"] [role="slider"] {
    background-color: #0a84ff;
}

/* Smaller label fonts */
.stLabel, label { font-size: 0.85rem; }
h1 { font-size: 2rem; }
h2 { font-size: 1.5rem; }
</style>
"""

THEMES = {"Dark": DARK, "Light": LIGHT}
