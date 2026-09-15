"""
Process-wide state for rate-limited services. app.py reloads core.translator on every run, which would reset a
class attribute; this module is not reloaded, so a block recorded on one run still holds on the next.
"""

# Until this time (time.time()), requests to Google's free translate endpoints are not sent.
google_blocked_until = 0.0
