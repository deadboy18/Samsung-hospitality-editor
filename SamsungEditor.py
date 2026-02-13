import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import struct
import os
import shutil
import datetime
import re
import csv

# --- BACKEND LOGIC ---
RECORD_SIZE = 320
MAX_RECORDS = 1000

class ChannelRecord:
    def __init__(self, index, data):
        self.original_index = index
        self.raw_data = bytearray(data)
        self.is_active = False
        self.ch_num = 0
        self.name = ""
        self.parse()

    def parse(self):
        self.ch_num = struct.unpack("<H", self.raw_data[0:2])[0]
        try:
            raw_name = self.raw_data[65:165]
            self.name = raw_name.decode("utf-16le").split('\x00')[0]
        except:
            self.name = ""
        
        if self.ch_num != 0 and self.ch_num != 0xFFFF and len(self.name) > 0:
            self.is_active = True

    def update(self, new_num=None, new_name=None):
        if new_num is not None: self.ch_num = int(new_num)
        if new_name is not None: self.name = str(new_name)
        struct.pack_into("<H", self.raw_data, 0, self.ch_num)
        name_bytes = self.name.encode("utf-16le")
        if len(name_bytes) > 100: name_bytes = name_bytes[:100]
        padding = 100 - len(name_bytes)
        self.raw_data[65:165] = name_bytes + (b'\x00' * padding)
        self.raw_data[319] = sum(self.raw_data[0:319]) % 256

    def delete(self):
        self.is_active = False
        self.ch_num = 0
        self.name = ""
        struct.pack_into("<H", self.raw_data, 0, 0)
        self.raw_data[65:165] = b'\x00' * 100

# --- MAIN APP ---
class SamsungEditorV6_3:
    def __init__(self, root):
        self.root = root
        self.root.title("Samsung Hospitality Editor v6.3")
        self.root.geometry("1100x700")
        
        self.colors = {"bg": "#f0f2f5", "header": "#ffffff", "accent": "#0078D4", "danger": "#d13438"}
        self.root.configure(bg=self.colors["bg"])
        
        self.records = []
        self.current_file = None
        self.sort_descending = False
        
        self.setup_ui()
        self.auto_detect_hardware()

    def setup_ui(self):
        # 1. Top Menu Bar
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # Help Menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="How to Clone (USB)", command=self.show_clone_help) # NEW
        help_menu.add_separator()
        help_menu.add_command(label="Map Types Explained", command=self.show_map_help)
        help_menu.add_separator()
        help_menu.add_command(label="About", command=lambda: messagebox.showinfo("About", "Samsung Hospitality Editor\nVersion 6.3\n\nDesigned for Hotel TV Reverse Engineering"))

        # 2. Header
        header = tk.Frame(self.root, bg=self.colors["header"], height=100, padx=20, pady=15)
        header.pack(fill=tk.X, pady=(0, 2))
        
        tk.Label(header, text="SAMSUNG CHANNEL EDITOR", bg=self.colors["header"], fg=self.colors["accent"], font=("Segoe UI", 18, "bold")).pack(side=tk.LEFT, anchor="n")
        self.lbl_hw_info = tk.Label(header, text="Waiting for files...", bg=self.colors["header"], fg="#444", justify=tk.RIGHT, font=("Consolas", 9))
        self.lbl_hw_info.pack(side=tk.RIGHT, anchor="n")

        # 3. Toolbar
        toolbar = tk.Frame(self.root, bg=self.colors["bg"], pady=10, padx=20)
        toolbar.pack(fill=tk.X)
        
        tk.Button(toolbar, text="📂 Open Map", command=self.load_map, bg="white", relief="groove", padx=10).pack(side=tk.LEFT, padx=5)
        tk.Button(toolbar, text="💾 Save Map", command=self.save_map, bg=self.colors["accent"], fg="white", relief="flat", padx=15).pack(side=tk.LEFT, padx=5)
        
        tk.Frame(toolbar, width=20, bg=self.colors["bg"]).pack(side=tk.LEFT) # Spacer
        tk.Button(toolbar, text="📤 Export CSV", command=self.export_csv, bg="#e1e1e1", padx=10).pack(side=tk.LEFT, padx=5)
        tk.Button(toolbar, text="📥 Import CSV", command=self.import_csv, bg="#e1e1e1", padx=10).pack(side=tk.LEFT, padx=5)

        tk.Label(toolbar, text="Search:", bg=self.colors["bg"]).pack(side=tk.LEFT, padx=(30, 5))
        self.search_var = tk.StringVar()
        self.search_var.trace("w", self.filter_grid)
        entry_search = tk.Entry(toolbar, textvariable=self.search_var, width=25)
        entry_search.pack(side=tk.LEFT)

        # 4. Grid
        frame_grid = tk.Frame(self.root, bg="white")
        frame_grid.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        cols = ("num", "name", "idx")
        self.tree = ttk.Treeview(frame_grid, columns=cols, show="headings", selectmode="extended")
        
        self.tree.heading("num", text="CH #", command=lambda: self.sort_tree_numeric("num"))
        self.tree.column("num", width=80, anchor="center")
        self.tree.heading("name", text="Channel Name (Right-Click for Options)", command=lambda: self.sort_tree_text("name"))
        self.tree.column("name", width=600)
        self.tree.column("idx", width=0, stretch=False) 

        vsb = ttk.Scrollbar(frame_grid, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<Double-1>", self.on_double_click)
        self.tree.bind("<Button-3>", self.show_context_menu)

        self.ctx_menu = tk.Menu(self.root, tearoff=0)
        self.ctx_menu.add_command(label="✏️ Edit Channel", command=self.on_double_click)
        self.ctx_menu.add_separator()
        self.ctx_menu.add_command(label="❌ Delete Selected", command=self.delete_channel)

        # 5. Status Bar
        self.status_var = tk.StringVar(value="Ready. Recommended: Open 'map-AirD' for Digital Channels.")
        tk.Label(self.root, textvariable=self.status_var, bg="#e1e1e1", anchor="w", padx=10).pack(fill=tk.X, side=tk.BOTTOM)

    def show_clone_help(self):
        steps = (
            "HOW TO EXTRACT (CLONE) FILES:\n\n"
            "1. Turn TV ON.\n"
            "2. Insert USB Drive.\n"
            "3. Enter Hotel Menu: Press [MUTE] > [1] > [1] > [9] > [ENTER].\n"
            "4. Select 'Clone TV to USB' and press Enter.\n"
            "5. Wait for success message, then remove USB.\n\n"
            "--------------------------------------------------\n\n"
            "HOW TO LOAD FILES TO TV:\n\n"
            "1. Turn TV ON.\n"
            "2. Insert USB Drive (with modified files).\n"
            "3. Enter Hotel Menu: Press [MUTE] > [1] > [1] > [9] > [ENTER].\n"
            "4. Select 'Clone USB to TV' and press Enter.\n"
            "5. The TV may turn OFF and ON again to apply settings."
        )
        messagebox.showinfo("Cloning Instructions", steps)

    def show_map_help(self):
        info = (
            "WHICH FILE SHOULD I EDIT?\n\n"
            "► map-AirD (Recommended)\n"
            "   • Contains DIGITAL Terrestrial channels.\n"
            "   • High quality, supports Names & EPG.\n"
            "   • Most common for modern hotels.\n\n"
            "► map-AirA\n"
            "   • Contains ANALOG Terrestrial channels.\n"
            "   • Only used for legacy systems.\n\n"
            "► map-CableD / map-CableA\n"
            "   • Same as above, but for CABLE signals."
        )
        messagebox.showinfo("Map Types Explained", info)

    def auto_detect_hardware(self):
        model = "Unknown"
        fw = "Unknown"
        panel_str = "Unknown"
        tech_details = ""

        if os.path.exists("ProductCloneInfo"):
            try:
                with open("ProductCloneInfo", "rb") as f:
                    f.seek(4)
                    raw = f.read().decode('utf-8', errors='ignore')
                    fw = raw.split('@')[0] if '@' in raw else "Unknown"
                    if '#' in raw:
                        model = raw.split('#')[1].split('%')[0]
            except: pass
        
        if os.path.exists("FADAT"):
            try:
                with open("FADAT", "rb") as f:
                    data = f.read()
                    full = "".join([chr(b) if 32 <= b <= 126 else "|" for b in data])
                    parts = [p for p in full.split('|') if len(p) > 3]
                    for p in parts:
                        if re.match(r'^\d{2}[A-Z]\d', p):
                            panel_str = p
                            break
                    if panel_str != "Unknown":
                        size = panel_str[:2]
                        series = panel_str[2:4]
                        rev = panel_str[4:]
                        tech_details = f"Display: {size}\" ({series} Series)\nRev: {rev}"
            except: pass
            
        display_text = f"MODEL: {model}\nFW: {fw}\nPANEL CODE: {panel_str}\n{tech_details}"
        self.lbl_hw_info.config(text=display_text)

    def load_map(self):
        path = filedialog.askopenfilename(filetypes=[("Samsung Map", "map-*"), ("All Files", "*.*")])
        if path:
            self.current_file = path
            self.records = []
            try:
                with open(path, "rb") as f:
                    for i in range(MAX_RECORDS):
                        raw = f.read(RECORD_SIZE)
                        if len(raw) != RECORD_SIZE: break
                        self.records.append(ChannelRecord(i, raw))
                self.refresh_grid()
                self.status_var.set(f"Loaded {len(self.records)} records from {os.path.basename(path)}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load: {str(e)}")

    def refresh_grid(self, query=""):
        self.tree.delete(*self.tree.get_children())
        active = [r for r in self.records if r.is_active]
        if query:
            active = [r for r in active if query.lower() in r.name.lower() or query in str(r.ch_num)]
        active.sort(key=lambda x: x.ch_num)
        for r in active:
            self.tree.insert("", "end", values=(r.ch_num, r.name, r.original_index))

    def filter_grid(self, *args):
        self.refresh_grid(self.search_var.get())

    def sort_tree_numeric(self, col):
        items = [(int(self.tree.set(k, col)), k) for k in self.tree.get_children('')]
        items.sort(reverse=self.sort_descending)
        for index, (val, k) in enumerate(items):
            self.tree.move(k, '', index)
        self.sort_descending = not self.sort_descending

    def sort_tree_text(self, col):
        items = [(self.tree.set(k, col).lower(), k) for k in self.tree.get_children('')]
        items.sort(reverse=self.sort_descending)
        for index, (val, k) in enumerate(items):
            self.tree.move(k, '', index)
        self.sort_descending = not self.sort_descending

    def show_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            if item not in self.tree.selection():
                self.tree.selection_set(item)
            self.ctx_menu.post(event.x_root, event.y_root)

    def on_double_click(self, event=None):
        sel = self.tree.selection()
        if not sel: return
        item = sel[0]
        vals = self.tree.item(item, 'values')
        idx = int(vals[2])
        rec = self.records[idx]

        edit_win = tk.Toplevel(self.root)
        edit_win.title(f"Edit CH {rec.ch_num}")
        edit_win.geometry("300x150")
        
        tk.Label(edit_win, text="Channel Number:").pack(pady=5)
        ent_num = tk.Entry(edit_win)
        ent_num.insert(0, rec.ch_num)
        ent_num.pack()
        
        tk.Label(edit_win, text="Channel Name:").pack(pady=5)
        ent_name = tk.Entry(edit_win)
        ent_name.insert(0, rec.name)
        ent_name.pack()

        def confirm():
            try:
                new_num = int(ent_num.get())
                new_name = ent_name.get()
                rec.update(new_num, new_name)
                self.refresh_grid(self.search_var.get())
                edit_win.destroy()
            except ValueError:
                messagebox.showerror("Error", "Channel Number must be an integer.")

        tk.Button(edit_win, text="Save", command=confirm, bg=self.colors["accent"], fg="white").pack(pady=10)

    def delete_channel(self):
        sel = self.tree.selection()
        if not sel: return
        count = len(sel)
        if not messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete {count} channel(s)?"): return
        for item in sel:
            idx = int(self.tree.item(item, 'values')[2])
            self.records[idx].delete()
        self.refresh_grid(self.search_var.get())
        self.status_var.set(f"Deleted {count} channels.")

    def export_csv(self):
        if not self.records:
            messagebox.showwarning("Warning", "No map loaded to export.")
            return

        messagebox.showinfo("Export Info", "IMPORTANT:\n\nYou can edit 'Channel Number' and 'Channel Name' in Excel.\n\nDO NOT edit the 'Index' column. This ID is required to link the data back to the original file.")

        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv")])
        if path:
            try:
                with open(path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(["Index (DO NOT EDIT)", "Channel Number", "Channel Name"])
                    
                    active = [r for r in self.records if r.is_active]
                    active.sort(key=lambda x: x.ch_num)
                    
                    for r in active:
                        writer.writerow([r.original_index, r.ch_num, r.name])
                
                messagebox.showinfo("Success", f"Exported {len(active)} channels to CSV.")
            except Exception as e:
                messagebox.showerror("Error", f"Export failed: {str(e)}")

    def import_csv(self):
        if not self.records:
            messagebox.showwarning("Warning", "Please load a map file first (to serve as the template).")
            return

        path = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv")])
        if path:
            try:
                updated_count = 0
                with open(path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    if "Index (DO NOT EDIT)" not in reader.fieldnames:
                        messagebox.showerror("Error", "Invalid CSV Format!\n\nThe 'Index (DO NOT EDIT)' column is missing.")
                        return

                    for row in reader:
                        try:
                            idx = int(row["Index (DO NOT EDIT)"])
                            new_num = int(row["Channel Number"])
                            new_name = row["Channel Name"]
                            if 0 <= idx < len(self.records):
                                self.records[idx].update(new_num, new_name)
                                updated_count += 1
                        except ValueError:
                            continue 

                self.refresh_grid()
                messagebox.showinfo("Success", f"Updated {updated_count} channels from CSV.")
            except Exception as e:
                messagebox.showerror("Error", f"Import failed: {str(e)}")

    def save_map(self):
        if not self.current_file: return
        folder = os.path.dirname(self.current_file)
        fname = os.path.basename(self.current_file)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        bak_path = os.path.join(folder, f"{fname}_{ts}.bak")
        try:
            shutil.copy(self.current_file, bak_path)
            with open(self.current_file, "wb") as f:
                for r in self.records:
                    f.write(r.raw_data)
            messagebox.showinfo("Success", f"Map saved!\nBackup: {os.path.basename(bak_path)}")
        except Exception as e:
            messagebox.showerror("Error", f"Save failed: {str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = SamsungEditorV6_3(root)
    root.mainloop()