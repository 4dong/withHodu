"""
Process-wide state for rate-limited services. Streamlit reloads core.translator when its file changes, which
would reset a class attribute; this module rarely changes, so a recorded block survives those reloads.
"""

# Until this time (time.time()), requests to Google's free translate endpoints are not sent.
google_blocked_until = 0.0
