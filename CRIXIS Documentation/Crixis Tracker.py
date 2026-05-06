import sqlite3
import tkinter as tk
from tkinter import messagebox, scrolledtext
import json
import os
import hashlib
import threading
import time
from datetime import datetime, timedelta
from dateutil import parser
from tkcalendar import DateEntry
from plyer import notification

# --- Configuration ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "Crixis.db")
SESSION_FILE = os.path.join(BASE_DIR, "session.json")

current_user = None

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS Users (username TEXT PRIMARY KEY, password TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS Subjects (username TEXT, name TEXT, UNIQUE(username, name))")
        cursor.execute("""CREATE TABLE IF NOT EXISTS Tasks (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            username TEXT, 
                            task_name TEXT, 
                            due_date TEXT, 
                            subject TEXT, 
                            time_start TEXT, 
                            time_end TEXT, 
                            task_details TEXT, 
                            is_done INTEGER DEFAULT 0
                            )""")
        cursor.execute("""CREATE TABLE IF NOT EXISTS Schedules (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            username TEXT, 
                            day TEXT, subject TEXT, 
                            time_start TEXT, 
                            time_end TEXT)""")
        conn.commit()

class CrixisApp:
    def __init__(self, root):
        self.root = root
        self.root.geometry("1200x850")
        self.root.title("Crixis Tracker")
        self.root.configure(bg="#f0f2f5")
        
        self.accent, self.pink, self.sidebar_bg = "#2196F3", "#E264A5", "#2c3e50"
        self.content_area = None
        self.stay_logged_in = False
        
        init_db()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.check_auto_login()
        
        self.stop_notifications = False
        self.notif_thread = threading.Thread(target=self.notification_watcher, daemon=True)
        self.notif_thread.start()

    def on_closing(self):
        if not hasattr(self, 'stay_logged_in') or not self.stay_logged_in:
            if os.path.exists(SESSION_FILE): os.remove(SESSION_FILE)
        self.stop_notifications = True
        self.root.destroy()

    def create_scrollable_view(self, title_text, btn_text=None, btn_cmd=None):
        self.clear_content()
        header = tk.Frame(self.content_area, bg="white", pady=15)
        header.pack(fill="x")
        tk.Label(header, text=title_text, font=("Arial", 22, "bold"), bg="white").pack()
        if btn_text and btn_cmd:
            tk.Button(header, text=btn_text, bg=self.accent if "Task" in btn_text else self.pink, 
                      fg="white", command=btn_cmd, padx=10).pack(pady=10)

        container = tk.Frame(self.content_area, bg="white")
        container.pack(fill="both", expand=True)
        
        canvas = tk.Canvas(container, bg="white", highlightthickness=0)
        scrollbar = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg="white")

        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        
        canvas.bind('<Configure>', lambda e: canvas.itemconfig(canvas_window, width=e.width))
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.root.bind_all("<MouseWheel>", lambda e: self._on_mousewheel(e, canvas))
        return scrollable_frame

    def _on_mousewheel(self, event, canvas):
        canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    # --- Auth Screen ---
    def show_auth_screen(self):
        for w in self.root.winfo_children(): w.destroy()
        f = tk.Frame(self.root, bg="#f0f2f5")
        f.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(f, text="CRIXIS", font=("Arial", 40, "bold"), fg=self.accent, bg="#f0f2f5").pack(pady=20)
        tk.Button(f, text="LOG IN", bg=self.pink, fg="white", width=20, height=2, command=lambda: self.auth_form("LOGIN")).pack(pady=5)
        tk.Button(f, text="SIGN UP", bg=self.accent, fg="white", width=20, height=2, command=lambda: self.auth_form("SIGNUP")).pack(pady=5)

    def auth_form(self, mode):
        for w in self.root.winfo_children(): w.destroy()
        f = tk.Frame(self.root, bg="white", padx=40, pady=40, bd=1, relief="solid")
        f.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(f, text=mode, font=("Arial", 18, "bold"), bg="white").pack(pady=10)
        tk.Label(f, text="Username", bg="white").pack(anchor="w")
        u_ent = tk.Entry(f, font=("Arial", 12), width=25); u_ent.pack(pady=(2, 10))
        tk.Label(f, text="Password", bg="white").pack(anchor="w")
        p_ent = tk.Entry(f, show="*", font=("Arial", 12), width=25); p_ent.pack(pady=(2, 10))
        stay_var = tk.BooleanVar(value=False)
        if mode == "LOGIN": tk.Checkbutton(f, text="Stay Logged In", variable=stay_var, bg="white").pack(pady=5)

        def handle():
            user, pw = u_ent.get().strip(), p_ent.get().strip()
            if not user or not pw: return
            hashed = hash_password(pw)
            with sqlite3.connect(DB_FILE) as conn:
                if mode == "LOGIN":
                    res = conn.execute("SELECT 1 FROM Users WHERE username=? AND password=?", (user, hashed)).fetchone()
                    if res:
                        global current_user; current_user = user
                        self.stay_logged_in = stay_var.get()
                        with open(SESSION_FILE, 'w') as file: json.dump({"last_user": user, "stay_logged": self.stay_logged_in}, file)
                        self.setup_main_layout()
                    else: messagebox.showerror("Error", "Login Failed")
                else:
                    try:
                        conn.execute("INSERT INTO Users VALUES (?,?)", (user, hashed))
                        conn.commit(); self.show_auth_screen()
                    except: messagebox.showerror("Error", "User exists")
        tk.Button(f, text="CONTINUE", bg=self.accent, fg="white", height=2, width=20, command=handle).pack(pady=10)
        tk.Button(f, text="Back", command=self.show_auth_screen, relief="flat").pack()

    def setup_main_layout(self):
        for w in self.root.winfo_children(): w.destroy()
        sb = tk.Frame(self.root, bg=self.sidebar_bg, width=200); sb.pack(side="left", fill="y"); sb.pack_propagate(False)
        tk.Label(sb, text=f"Hi, {current_user}", fg="white", bg=self.sidebar_bg, font=("Arial", 10, "bold"), pady=20).pack()
        nav = [("🚀 Tasks", self.show_pending_view), ("📅 Schedule", self.show_schedule_view), 
               ("📚 Subjects", self.show_subjects_view), ("✅ History", self.show_completed_view), ("🚪 Logout", self.logout)]
        for t, c in nav: tk.Button(sb, text=t, bg="#34495e", fg="white", relief="flat", height=2, command=c).pack(fill="x", pady=2, padx=10)
        self.content_area = tk.Frame(self.root, bg="white"); self.content_area.pack(side="right", fill="both", expand=True)
        self.show_pending_view()

    def show_pending_view(self):
        sf = self.create_scrollable_view("Upcoming Tasks", "+ New Task", self.task_form)
        with sqlite3.connect(DB_FILE) as conn:
            tasks = conn.execute("SELECT id, task_name, due_date, subject, time_start, time_end, task_details FROM Tasks WHERE username=? AND is_done=0 ORDER BY due_date ASC", (current_user,)).fetchall()
        for t in tasks:
            f = tk.Frame(sf, bg="#f9f9f9", pady=10, padx=20, bd=1, relief="groove"); f.pack(fill="x", padx=40, pady=5)
            lbl = tk.Label(f, text=f"📌 {t[1]} ({t[3]})\nDue: {t[2]} | {t[4]}-{t[5]}", font=("Arial", 10), bg="#f9f9f9", justify="left", cursor="hand2")
            lbl.pack(side="left"); lbl.bind("<Button-1>", lambda e, d=t: self.show_task_details(d))
            tk.Button(f, text="🗑️", fg="red", relief="flat", command=lambda i=t[0]: self.delete_task(i)).pack(side="right", padx=5)
            tk.Button(f, text="Edit", command=lambda d=t: self.task_form(d)).pack(side="right", padx=5)
            tk.Button(f, text="Done", bg="#2ecc71", fg="white", command=lambda i=t[0]: self.mark_done(i)).pack(side="right")

    # --- Task Details Box (Fixed Narrow/Card Style) ---
    def show_task_details(self, t):
        win = tk.Toplevel(self.root)
        win.title("Task Details")
        win_width, win_height = 360, 520
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (win_width // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (win_height // 2)
        win.geometry(f"{win_width}x{win_height}+{x}+{y}")
        win.configure(bg="white"); win.resizable(False, False)

        outer_pad = tk.Frame(win, bg="white", padx=15, pady=15); outer_pad.pack(fill="both", expand=True)

        tk.Label(outer_pad, text=t[1], font=("Arial", 14, "bold"), bg="white", fg=self.accent, wraplength=310, justify="left").pack(anchor="w")
        tk.Label(outer_pad, text=f"Subject: {t[3]}", font=("Arial", 10), bg="white", fg="#555").pack(anchor="w", pady=(5, 0))
        tk.Label(outer_pad, text=f"Due: {t[2]} | {t[4]}-{t[5]}", font=("Arial", 9), bg="white", fg="gray").pack(anchor="w")

        tk.Frame(outer_pad, height=1, bg="#eeeeee").pack(fill="x", pady=15)
        tk.Label(outer_pad, text="NOTES", font=("Arial", 8, "bold"), bg="white", fg="#999").pack(anchor="w", pady=(0, 5))
        
        border_frame = tk.Frame(outer_pad, bg="#cccccc", padx=1, pady=1); border_frame.pack(fill="both", expand=True)
        st = scrolledtext.ScrolledText(border_frame, font=("Arial", 10), bg="#fcfcfc", bd=0, highlightthickness=0, padx=10, pady=10, wrap="word")
        st.insert("1.0", t[6] if (len(t) > 6 and t[6]) else "No additional details provided.")
        st.config(state="disabled"); st.pack(fill="both", expand=True)

        tk.Button(outer_pad, text="CLOSE", width=12, bg="#ecf0f1", fg="#333", font=("Arial", 9, "bold"), relief="flat", command=win.destroy).pack(pady=(15, 0))
        win.transient(self.root); win.grab_set()

    def task_form(self, task=None):
        sf = self.create_scrollable_view("Task Editor")
        
        def create_field(label_text, default_val=None, is_text=False):
            tk.Label(sf, text=label_text, bg="white", font=("Arial", 10, "bold")).pack(anchor="w", padx=100, pady=(10, 0))
            if is_text:
                b_frame = tk.Frame(sf, bg="#cccccc", padx=1, pady=1); b_frame.pack(pady=5, padx=100, fill="x")
                txt = tk.Text(b_frame, height=8, font=("Arial", 11), bd=0, highlightthickness=0)
                txt.pack(fill="both")
                if default_val: txt.insert("1.0", default_val)
                return txt
            else:
                ent = tk.Entry(sf, font=("Arial", 11), width=45); ent.pack(pady=5)
                if default_val: ent.insert(0, default_val)
                return ent

        n_ent = create_field("Task Name", task[1] if task else None)
        tk.Label(sf, text="Subject", bg="white", font=("Arial", 10, "bold")).pack(anchor="w", padx=100)
        subs = self.get_my_subjects(); sub_v = tk.StringVar(value=task[3] if task else subs[0])
        tk.OptionMenu(sf, sub_v, *subs).pack(pady=5)

        tk.Label(sf, text="Due Date", bg="white", font=("Arial", 10, "bold")).pack(anchor="w", padx=100)
        cal = DateEntry(sf, font=("Arial", 11), width=43, date_pattern='yyyy-mm-dd'); cal.pack(pady=5)
        if task: cal.set_date(parser.parse(task[2]))

        h1, m1 = self.create_apple_scroller(sf, "Start Time")
        h2, m2 = self.create_apple_scroller(sf, "End Time")
        if task:
            for h, m, t_str in [(h1, m1, task[4]), (h2, m2, task[5])]:
                h.delete(0,'end'); h.insert(0, t_str.split(":")[0]); m.delete(0,'end'); m.insert(0, t_str.split(":")[1])

        d_txt = create_field("Task Details", task[6] if task and task[6] else "", is_text=True)

        def save():
            try:
                t1, t2 = f"{int(h1.get()):02d}:{int(m1.get()):02d}", f"{int(h2.get()):02d}:{int(m2.get()):02d}"
                with sqlite3.connect(DB_FILE) as conn:
                    if task:
                        conn.execute("UPDATE Tasks SET task_name=?, due_date=?, subject=?, time_start=?, time_end=?, task_details=? WHERE id=?", 
                                     (n_ent.get(), cal.get(), sub_v.get(), t1, t2, d_txt.get("1.0","end-1c"), task[0]))
                    else:
                        conn.execute("INSERT INTO Tasks (username, task_name, due_date, subject, time_start, time_end, task_details) VALUES (?,?,?,?,?,?,?)", 
                                     (current_user, n_ent.get(), cal.get(), sub_v.get(), t1, t2, d_txt.get("1.0","end-1c")))
                    conn.commit()
                self.show_pending_view()
            except: messagebox.showwarning("Input Error", "Check your inputs and time formats.")

        tk.Button(sf, text="SAVE TASK", bg=self.accent, fg="white", width=25, height=2, command=save).pack(pady=30)

    def show_schedule_view(self):
        sf = self.create_scrollable_view("Weekly Schedule", "+ Add Class", self.class_form)
        grid = tk.Frame(sf, bg="white"); grid.pack(fill="both", expand=True, padx=10)
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        for i, d in enumerate(days):
            grid.columnconfigure(i, weight=1)
            tk.Label(grid, text=d, font=("Arial", 8, "bold"), bg="#eceff1", pady=10).grid(row=0, column=i, sticky="nsew", padx=1, pady=5)
        with sqlite3.connect(DB_FILE) as conn:
            classes = conn.execute("SELECT id, day, subject, time_start, time_end FROM Schedules WHERE username=?", (current_user,)).fetchall()
        for i, d in enumerate(days):
            day_classes = sorted([c for c in classes if c[1] == d], key=lambda x: x[3])
            for j, c_data in enumerate(day_classes):
                box = tk.Frame(grid, bg="#e3f2fd", pady=5, bd=1, relief="flat"); box.grid(row=j+1, column=i, sticky="new", padx=1, pady=1)
                lbl = tk.Label(box, text=f"{c_data[2]}\n{c_data[3]}-{c_data[4]}", font=("Arial", 8), bg="#e3f2fd", cursor="hand2")
                lbl.pack(); lbl.bind("<Button-1>", lambda e, cd=c_data: self.class_form(cd))
                tk.Button(box, text="🗑️", fg="red", bg="#e3f2fd", relief="flat", font=("Arial", 7), command=lambda cid=c_data[0]: self.delete_class(cid)).pack()

    def show_subjects_view(self):
        sf = self.create_scrollable_view("Subjects")
        af = tk.Frame(sf, bg="white", pady=10); af.pack(fill="x")
        tk.Label(af, text="Add New Subject:", bg="white", font=("Arial", 10, "bold")).pack()
        ent = tk.Entry(af, font=("Arial", 11), bd=1, relief="solid", width=30); ent.pack(pady=5)
        def add():
            n = ent.get().strip()
            if not n: return
            with sqlite3.connect(DB_FILE) as conn:
                try: conn.execute("INSERT INTO Subjects VALUES (?,?)", (current_user, n)); conn.commit()
                except: pass
            self.show_subjects_view()
        tk.Button(af, text="Add", bg=self.accent, fg="white", command=add).pack()
        for s in self.get_my_subjects():
            if s == "General": continue
            f = tk.Frame(sf, bg="#fcfcfc", pady=4, padx=15); f.pack(fill="x", padx=150, pady=1)
            tk.Label(f, text=s, bg="#fcfcfc").pack(side="left")
            tk.Button(f, text="✕", fg="#999", relief="flat", bg="#fcfcfc", command=lambda x=s: self.delete_subject(x)).pack(side="right")

    def class_form(self, cl=None):
        sf = self.create_scrollable_view("Class Editor")
        tk.Label(sf, text="Day of Week", bg="white", font=("Arial", 10, "bold")).pack(anchor="w", padx=100)
        day_v = tk.StringVar(value=cl[1] if cl else "Monday")
        tk.OptionMenu(sf, day_v, "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday").pack(pady=5)
        tk.Label(sf, text="Subject", bg="white", font=("Arial", 10, "bold")).pack(anchor="w", padx=100)
        subs = self.get_my_subjects(); sub_v = tk.StringVar(value=cl[2] if cl else subs[0])
        tk.OptionMenu(sf, sub_v, *subs).pack(pady=5)
        h1, m1 = self.create_apple_scroller(sf, "Start Time"); h2, m2 = self.create_apple_scroller(sf, "End Time")
        if cl:
            for h, m, t_str in [(h1, m1, cl[3]), (h2, m2, cl[4])]:
                h.delete(0,'end'); h.insert(0, t_str.split(":")[0]); m.delete(0,'end'); m.insert(0, t_str.split(":")[1])
        def save():
            try:
                t1, t2 = f"{int(h1.get()):02d}:{int(m1.get()):02d}", f"{int(h2.get()):02d}:{int(m2.get()):02d}"
                with sqlite3.connect(DB_FILE) as conn:
                    if cl: conn.execute("UPDATE Schedules SET day=?, subject=?, time_start=?, time_end=? WHERE id=?", (day_v.get(), sub_v.get(), t1, t2, cl[0]))
                    else: conn.execute("INSERT INTO Schedules (username, day, subject, time_start, time_end) VALUES (?,?,?,?,?)", (current_user, day_v.get(), sub_v.get(), t1, t2))
                    conn.commit()
                self.show_schedule_view()
            except: messagebox.showwarning("Input Error", "Check your time inputs.")
        tk.Button(sf, text="SAVE CLASS", bg=self.pink, fg="white", width=25, height=2, command=save).pack(pady=20)

    def check_auto_login(self):
        global current_user
        if os.path.exists(SESSION_FILE):
            try:
                with open(SESSION_FILE, 'r') as f:
                    data = json.load(f); u = data.get("last_user")
                    self.stay_logged_in = data.get("stay_logged", False)
                if u: current_user = u; self.setup_main_layout(); return
            except: pass
        self.show_auth_screen()

    def notification_watcher(self):
        last_checked = ""
        while not self.stop_notifications:
            if current_user:
                now = datetime.now(); cur_t = now.strftime("%H:%M")
                if cur_t != last_checked:
                    with sqlite3.connect(DB_FILE) as conn:
                        tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")
                        t_due = conn.execute("SELECT task_name FROM Tasks WHERE username=? AND due_date=? AND is_done=0", (current_user, tomorrow)).fetchall()
                        for (tn,) in t_due: notification.notify(title="Due Tomorrow", message=f"Don't forget: {tn}")
                    last_checked = cur_t
            time.sleep(30)

    def create_apple_scroller(self, parent, label_text):
        fr = tk.Frame(parent, bg="white", pady=5); fr.pack()
        tk.Label(fr, text=label_text, bg="white", font=("Arial", 9, "bold")).pack()
        c = tk.Frame(fr, bg="#F5F5F7", padx=5, pady=5); c.pack()
        h = tk.Spinbox(c, from_=0, to=23, format="%02.0f", width=4, font=("Arial", 12), bd=0, wrap=True); h.pack(side="left")
        m = tk.Spinbox(c, from_=0, to=59, format="%02.0f", width=4, font=("Arial", 12), bd=0, wrap=True); m.pack(side="left")
        return h, m

    def show_completed_view(self):
        sf = self.create_scrollable_view("History")
        with sqlite3.connect(DB_FILE) as conn:
            done = conn.execute("SELECT id, task_name, subject, due_date FROM Tasks WHERE username=? AND is_done=1 ORDER BY due_date DESC", (current_user,)).fetchall()
        for t in done:
            f = tk.Frame(sf, bg="#e8f5e9", pady=10, padx=20); f.pack(fill="x", padx=60, pady=5)
            tk.Label(f, text=f"✅ {t[3]} | {t[2]}: {t[1]}", bg="#e8f5e9").pack(side="left")
            tk.Button(f, text="Restore", command=lambda i=t[0]: self.mark_pending(i)).pack(side="right")
            tk.Button(f, text="🗑️", fg="red", relief="flat", bg="#e8f5e9", command=lambda i=t[0]: self.delete_task(i, True)).pack(side="right", padx=10)

    def get_my_subjects(self):
        with sqlite3.connect(DB_FILE) as conn:
            res = conn.execute("SELECT name FROM Subjects WHERE username=?", (current_user,)).fetchall()
            return [r[0] for r in res] if res else ["General"]

    def delete_subject(self, n):
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("DELETE FROM Subjects WHERE username=? AND name=?", (current_user, n)); conn.commit()
        self.show_subjects_view()

    def mark_done(self, tid):
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("UPDATE Tasks SET is_done=1 WHERE id=?", (tid,)); conn.commit()
        self.show_pending_view()

    def mark_pending(self, tid):
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("UPDATE Tasks SET is_done=0 WHERE id=?", (tid,)); conn.commit()
        self.show_completed_view()

    def delete_task(self, tid, h=False):
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("DELETE FROM Tasks WHERE id=?", (tid,)); conn.commit()
        self.show_completed_view() if h else self.show_pending_view()

    def delete_class(self, cid):
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("DELETE FROM Schedules WHERE id=?", (cid,)); conn.commit()
        self.show_schedule_view()

    def clear_content(self):
        if self.content_area:
            for w in self.content_area.winfo_children(): w.destroy()

    def logout(self):
        if os.path.exists(SESSION_FILE): os.remove(SESSION_FILE)
        global current_user; current_user = None; self.show_auth_screen()

if __name__ == "__main__":
    root = tk.Tk(); 
    app = CrixisApp(root); 
    root.mainloop()