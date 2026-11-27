import os
import sqlite3
import time
import traceback 
from datetime import date, datetime, timedelta

from jnius import autoclass

# main.py passes the database path when it start this service
DBPATH = os.environ.get("PYTHON_SERVICE_ARGUMENT", "")
SENTFILE = DBPATH + ".sent"
SEND_HOUR = 20

# keep in sync with META in main.py
GROUPS = {
    "Uplifted": ["bliss", "happy", "grateful", "excited"],
    "Settled": ["calm", "content", "peaceful"],
    "Tense": ["anxious", "angry", "restless", "overwhelmed"],
    "Low": ["sad", "lonely", "tired", "empty"],
    "Flat": ["numb", "bored", "detached"],
}
EMO2META = {e: m for m, es in GROUPS.items() for e in es}
SLOTNAMES = ["Morning", "Afternoon", "Evening", "Night"]


def slot_index(h):
    if 5 <= h < 12:
        return 0
    if 12 <= h < 17:
        return 1
    if 17 <= h < 21:
        return 2
    return 3
    
    
def summary(s, e):
    con = sqlite3.connect(DBPATH)
    rows = con.execute("SELECT ts, emotion FROM logs WHERE ts >= ? AND ts < ?",
                      (s.isoformat(), e.isoformat())).fetchall()
    con.close()
    if not rows:
        return "Nothing was logged in this period."
    total = len(rows)
    counts = {}
    slots = {}
    for ts, emo in rows:
        m = EMO2META.get(emo, "Other")
        counts[m] = counts.get(m, 0) + 1
        k = (m, slot_index(int(ts[11:13])))
        slots[k] = slots.get(k, 0) + 1
    order = sorted(counts, key=counts.get, reverse=True)
    text = str(total) + " logged: " + ", ".join(
        m + " " + str(round(100 * counts[m] / total)) + "%" for m in order)
    top = order[0]
    best = max(range(4), key=lambda i: slots.get((top, i), 0))
    return text + ". " + top + " peaked in the " + SLOTNAMES[best] + "."
    
    
def due_reports(today):
    tommorow = today + timedelta(days=1)
    monday = today - timedelta(days=today.weekday())
    out = [(1, "Daily mood report", today, tommorow)]
    if today.weekday() == 6:
        out.append((2, "Weekly mood report", monday, monday + timedelta(days=7)))
    if tommorow.day == 1:
        out.append((3, "Monthly mood report", today.replace(day=1), tommorow))
    if today.month == 12 and today.day == 31:
        out.append((4, "Yearly mood report", date(today.year, 1, 1), tommorow))
    return out
    
    
def notify(nid, title, text):
    PythonService = autoclass("org.kivy.android.PythonService")
    Context = autoclass("android.content.Context")
    NotificationManager = autoclass("android.app.NotificationManager")
    NotificationChannel = autoclass("android.app.NotificationChannel")
    Builder = autoclass("android.app.Notification$Builder")
    BigText = autoclass("android.app.Notification$BigTextStyle")
    PendingIntent = autoclass("android.app.PendingIntent")
    
    ctx = PythonService.mService
    nm = ctx.getSystemService(Context.NOTIFICATION_SERVICE)
    chan = NotificationChannel("mood_reports", "Mood reports",
                               NotificationManager.IMPORTANCE_DEFAULT)
    nm.createNotificationChannel(chan)
    
    intent = ctx.getPackageManager().getLaunchIntentForPackage(ctx.getPackageName())
    pi = PendingIntent.getActivity(
        ctx, 0, intent, PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT)
        
    b = Builder(ctx, "mood_reports")
    b.setContentTitle(title)
    b.setContentText(text)
    b.setStyle(BigText().bigText(text))
    b.setSmallIcon(ctx.getApplicationInfo().icon)
    b.setContentIntent(pi)
    b.setAutoCancel(True)
    nm.notify(nid, b.build())
    
    
def already_sent(today):
    try:
        with open(SENTFILE) as f:
            return f.read().strip() == today.isoformat()
    except Exception:
        return False
        
        
while True:
    try:
        now = datetime.now()
        if now.hour >= SEND_HOUR and not already_sent(now.date()):
            for nid, title, s, e in due_reports(now.date()):
                notify(nid, title, summary(s, e))
            with open(SENTFILE, "w") as f:
                f.write(now.date().isoformat())
    except Exception:
        traceback.print_exc()
    time.sleep(30)
