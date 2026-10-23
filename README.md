# Shopee Conversion Notifications

A small web app for Shopee Affiliate conversion reports and Telegram summaries. It polls the AddLiveTag conversions API every 10 minutes and sends a Telegram message when today's order count or estimated commission changes. It also sends a summary after monitoring starts and after the Vietnam date rolls over, including zero-order days. GMV is omitted from Telegram messages.

## Deploy

Deploy this repository as a Python web service on a host that supports a `Procfile` and provides a `PORT` environment variable.

Set this environment variable in the hosting dashboard before deploying:

- `DASHBOARD_PASSWORD`: a strong password for the web dashboard. The username is `admin`.

The app binds to `0.0.0.0` when `PORT` is provided and refuses to start on a public host if `DASHBOARD_PASSWORD` is missing. The host should provide HTTPS so browser credentials and API keys are protected in transit.

After deployment, open the service URL and sign in with username `admin` and the password you configured. In the app:

1. Enter the AddLiveTag API key. Optionally enter an account ID; leave it blank to include all Shopee accounts.
2. Create a Telegram bot with `@BotFather`, send `/start` to the bot, then enter its token and use **Find Chat ID**.
3. Send a test Telegram message, then click **Start phone notifications**.

Dashboard fields (including API keys and tokens) are saved in this browser’s local storage so they remain after a page reload. They are also sent to the server over HTTPS for API requests and held in process memory while monitoring; they are not stored in this repository. Use **Clear saved information** to remove them from this browser. The notification monitor also runs in process memory. A page reload restores the saved fields and shows whether monitoring is still running. If the host restarts or sleeps the service, open the dashboard and start monitoring again. Use an always-on host for uninterrupted notifications.

## Local run

Requires Python 3.9 or later. Run:

```sh
python3 app.py
```

Then open <http://127.0.0.1:8765>. Local mode does not require `DASHBOARD_PASSWORD` because the app only listens on loopback.
