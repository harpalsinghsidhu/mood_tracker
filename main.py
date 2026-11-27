from kivy.utils import platform
import calendar
import os
import sqlite3
from datetime import date, datetime, timedelta

from kivy.app import App
from kivy.core.window import Window 
from kivy.graphics import Color, Ellipse, Rectangle
from kivy.metrics import dp
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button 
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label 
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

# --------------- meta moods and emotions -------------
META = [
    ("Uplifted", (1.0, 0.78, 0.2, 1), ["bliss", "happy", "grateful", "excited"]),
    ("Settled", (0.3, 0.75, 0.5, 1), ["calm", "content", "peaceful"]),
    ("Tense", (0.9, 0.3, 0.3, 1), ["anxious", "angry", "restless", "overwhelmed"]),
    ("Low", (0.3, 0.5, 0.9, 1), ["sad", "lonely", "tired", "empty"]),
    ("Flat", (0.6, 0.6, 0.65, 1), ["numb", "bored", "detached"]),
]
EMO2META = {e: name for name, col, emos, in META for e in emos}
META_COL = {name: col for name, col, emos, in META}

# Morning 5-12, Afternoon 12-17, Evening 17-21, Night 21-5
SLOTS = ["Morn", "Aft", "Eve", "Night"]


def slot(hour):
    if 5 <= hour < 12:
        return SLOTS[0]
    if 12 <= hour < 17:
        return SLOTS[1]
    if 17 <= hour < 21:
        return SLOTS[2]
    return SLOTS[3]
    
    
# --------------- database ---------------
DBPATH = ""


def q(sql, args=(), commit=False):
    con = sqlite3.connect(DBPATH)
    rows = con.execute(sql, args).fetchall()
    if commit:
        con.commit()
    con.close()
    return rows
    
    
def add_log(emotion):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    q("INSERT INTO logs(ts, emotion) VALUES(?, ?)", (now, emotion), commit=True)
    
    
def undo_last():
    q("DELETE FROM logs WHERE id = (SELECT MAX(id) FROM logs)", commit=True)
    
    
def period_range(kind, off):
    today = date.today()
    if kind == "Day":
        s = today + timedelta(days=off)
        e = s + timedelta(days=1)
        label = s.strftime("%a %d %b %Y")
    elif kind == "Week":
        s = today - timedelta(days=today.weekday()) + timedelta(weeks=off)
        e = s + timedelta(days=7)
        label = s.strftime("%d %b") + " - " + (e - timedelta(days=1)).strftime("%d %b %Y")
    elif kind == "Month":
        m = today.year * 12 + today.month - 1 + off
        y, mo = divmod(m, 12)
        s = date(y, mo + 1, 1)
        y2, mo2 = divmod(m + 1, 12)
        e = date(y2, mo2 + 1, 1)
        label = s.strftime("%B %Y")
    else:
        y = today.year + off
        s = date(y, 1, 1)
        e = date(y + 1, 1, 1)
        label = str(y)
    return s, e, label
    
    
# ------------- small widgets ------------
class CircleButton(ButtonBehavior, Label):
    def __init__(self, rgba, **kw):
        super().__init__(**kw)
        self.base = rgba
        self.color = (0.05, 0.05, 0.08, 1)
        self.bold = True
        self.font_size = "12sp"
        with self.canvas.before:
            self.clr = Color(*rgba)
            self.el = Ellipse()
        self.bind(pos=self.upd, size=self.upd)
        
    def upd(self, *a):
        d = min(self.width, self.height) * 0.95
        self.el.size = (d, d)
        self.el.pos = (self.center_x - d / 2, self.center_y - d / 2)
        
    def on_press(self):
        self.clr.rgba = (1, 1, 1, 1)
        
    def on_release(self):
        self.clr.rgba = self.base 
        
    
class Cell(Label):
    def __init__(self, rgb, strength, **kw):
        super().__init__(**kw)
        with self.canvas.before:
            Color(rgb[0], rgb[1], rgb[2], 0.12 + 0.88 * strength)
            self.r = Rectangle()
        self.bind(pos=self.upd, size=self.upd)
        
    def upd(self, *a):
        self.r.pos = self.pos
        self.r.size = self.size 
        
        
class Bar(Widget):
    def __init__(self, frac, rgba, **kw):
        super().__init__(**kw)
        self.frac = frac 
        self.rgba = rgba
        self.bind(pos=self.draw, size=self.draw)
        
    def draw(self, *a):
        self.canvas.clear()
        y = self.center_y - dp(7)
        with self.canvas:
            Color(1, 1, 1, 0.08)
            Rectangle(pos=(self.x, y), size=(self.width, dp(14)))
            Color(*self.rgba)
            Rectangle(pos=(self.x, y), size=(self.width * self.frac, dp(14)))
            
            
# ----------------- main screen ----------------
class MainScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        root = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))
        root.add_widget(Label(text="How are you feeling?", font_size="22sp",
                              size_hint_y=None, height=dp(44)))
        self.status = Label(text="Tap a circle when you feel it", size_hint_y=None,
                            height=dp(30), color=(0.7, 0.7, 0.75, 1))
        root.add_widget(self.status)
        
        sv = ScrollView()
        box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(4))
        box.bind(minimum_height=box.setter("height"))
        for name, col, emos, in META:
            box.add_widget(Label(text=name, color=col, bold=True, font_size="16sp",
                                 size_hint_y=None, height=dp(30)))
            grid = GridLayout(cols=3, size_hint_y=None, spacing=dp(6))
            grid.bind(minimum_height=grid.setter("height"))
            for e in emos:
                b = CircleButton(col, text=e, size_hint_y=None, height=dp(100))
                b.bind(on_release=lambda w, e=e: self.log(e))
                grid.add_widget(b)
            box.add_widget(grid)
        sv.add_widget(box)
        root.add_widget(sv)
        
        bar = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(8))
        for txt, fn in (("Undo last", self.undo), ("Reports", self.reports)):
            b = Button(text=txt)
            b.bind(on_release=fn)
            bar.add_widget(b)
        root.add_widget(bar)
        self.add_widget(root)
        
    def log(self, emotion):
        add_log(emotion)
        n = q("SELECT COUNT(*) FROM logs WHERE ts >= ?", (date.today().isoformat(),))[0][0]
        self.status.text = "Logged " + emotion + " | " + str(n) + " today"
        
    def undo(self, *a):
        undo_last()
        self.status.text = "Last entry removed"
        
    def reports(self, *a):
        self.manager.get_screen("report").refresh()
        self.manager.current = "report"
        
        
# ---------------- report screen -----------------
class ReportScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.kind = "Week"
        self.off = 0
        root = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))
        
        tabs = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(4))
        self.tabs = {}
        for k in ("Day", "Week", "Month", "Year"):
            b = Button(text=k)
            b.bind(on_release=lambda w, k=k: self.set_kind(k))
            tabs.add_widget(b)
            self.tabs[k] = b
        root.add_widget(tabs)
        
        nav = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(4))
        prev = Button(text="<", size_hint_x=None, width=dp(56))
        prev.bind(on_release=lambda w: self.shift(-1))
        nxt = Button(text=">", size_hint_x=None, width=dp(56))
        nxt.bind(on_release=lambda w: self.shift(1))
        self.title = Label(font_size="16sp")
        nav.add_widget(prev)
        nav.add_widget(self.title)
        nav.add_widget(nxt)
        root.add_widget(nav)
        
        sv = ScrollView()
        self.body = BoxLayout(orientation="vertical", size_hint_y=None,
                              spacing=dp(6), padding=dp(4))
        self.body.bind(minimum_height=self.body.setter("height"))
        sv.add_widget(self.body)
        root.add_widget(sv)
        
        back = Button(text="Back", size_hint_y=None, height=dp(48))
        back.bind(on_release=lambda w: setattr(self.manager, "current", "main"))
        root.add_widget(back)
        self.add_widget(root)
        
    def set_kind(self, k):
        self.kind = k
        self.off = 0
        self.refresh()
        
    def shift(self, d):
        self.off += d
        self.refresh()
        
    def head(self, t):
        return Label(text=t, bold=True, font_size="16sp", size_hint_y=None, height=dp(34))
        
    def refresh(self):
        for k, b in self.tabs.items():
            b.background_color = (0.3, 0.6, 1, 1) if k == self.kind else (1, 1, 1, 1)
        s, e, label = period_range(self.kind, self.off)
        self.title.text = label
        body = self.body 
        body.clear_widgets()
        rows = q("SELECT ts, emotion FROM logs WHERE ts >= ? AND ts < ?",
                 (s.isoformat(), e.isoformat()))
        if not rows:
            body.add_widget(Label(text="No entries in this period", size_hint_y=None,
                                  height=dp(60)))
            return 
            
        total = len(rows)
        keylen = 10 if self.kind in ("Day", "Week", "Month") else 7
        meta_count = {m[0]: 0 for m in META}
        emo_count = {}
        slot_count = {}
        per_key = {}
        for ts, emo in rows:
            meta = EMO2META[emo]
            meta_count[meta] += 1
            emo_count[emo] = emo_count.get(emo, 0) + 1
            sk = (meta, slot(int(ts[11:13])))
            slot_count[sk] = slot_count.get(sk, 0) + 1
            d = per_key.setdefault(ts[:keylen], {})
            d[meta] = d.get(meta, 0) + 1
            
        # overall mood
        body.add_widget(self.head("Overall mood (" + str(total) + " logged)"))
        for name, col, emos in META:
            c = meta_count[name]
            row = BoxLayout(size_hint_y=None, height=dp(28), spacing=dp(6))
            row.add_widget(Label(text=name, color=col, size_hint_x=None, width=dp(80)))
            row.add_widget(Bar(c / total, col))
            row.add_widget(Label(text=str(c) + " (" + str(round(100 * c / total)) + "%)",
                                 size_hint_x=None, width=dp(80)))
            body.add_widget(row)
            detail = ", ".join(x + " " + str(emo_count[x]) for x in emos if x in emo_count)
            if detail:
                body.add_widget(Label(text=detail, font_size="12sp",
                                      color=(0.65, 0.65, 0.7, 1),
                                      size_hint_y=None, height=dp(20)))
            
        # time of day grid
        body.add_widget(self.head("Time of day"))
        g = GridLayout(cols=5, size_hint_y=None, height=dp(36) * 6, spacing=dp(2))
        g.add_widget(Label())
        for sl in SLOTS:
            g.add_widget(Label(text=sl, font_size="12sp"))
        mx = max(slot_count.values())
        for name, col, emos in META:
            g.add_widget(Label(text=name, color=col, font_size="12sp"))
            for sl in SLOTS:
                n = slot_count.get((name, sl), 0)
                g.add_widget(Cell(col, n / mx if n else 0, text=str(n) if n else "-"))
        body.add_widget(g)
        
        # dominant mood per day (or per month for a year)
        if self.kind != "Day":
            body.add_widget(self.head("Dominant mood by " +
                                      ("month" if self.kind == "Year" else "day")))
            keys = []
            if self.kind == "Year":
                for m in range(1, 13):
                    keys.append((calendar.month_abbr[m], str(s.year) + "-" + str(m).zfill(2)))
            else:
                d = s
                while d < e:
                    keys.append((str(d.day), d.isoformat()))
                    d += timedelta(days=1)
            cols = 6 if self.kind == "Year" else 7
            nrows = -(-len(keys) // cols)
            cal = GridLayout(cols=cols, size_hint_y=None, height=dp(40) * nrows,
                             spacing=dp(2))
            for lab, key in keys:
                d = per_key.get(key)
                if d: 
                    top = max(d, key=d.get)
                    cal.add_widget(Cell(META_COL[top], 1, text=lab))
                else:
                    cal.add_widget(Cell((1, 1, 1), 0, text=lab))
            body.add_widget(cal)
            
def start_service():
    if platform != "android":
        return
    try:
        from android.permissions import request_permissions
        from jnius import autoclass
        request_permissions(["android.permission.POST_NOTIFICATIONS"])
        act = autoclass("org.kivy.android.PythonActivity").mActivity
        svc = autoclass(act.getPackageName() + ".ServiceReminder")
        svc.start(act, DBPATH)
    except Exception as ex:
        print("service start failed", ex)

# ------------- app --------------
class MoodApp(App):
    def build(self):
        global DBPATH
        Window.clearcolor = (0.08, 0.08, 0.11, 1)
        DBPATH = os.path.join(self.user_data_dir, "mood.db")
        q("CREATE TABLE IF NOT EXISTS logs "
          "(id INTEGER PRIMARY KEY, ts TEXT, emotion TEXT)", commit=True)
        start_service()
        sm = ScreenManager()
        sm.add_widget(MainScreen(name="main"))
        sm.add_widget(ReportScreen(name="report"))
        return sm
        
        
MoodApp().run()


