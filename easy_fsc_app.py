from __future__ import annotations

import shutil
import subprocess
import sys
import tkinter as tk
import zipfile
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from fsc_core import (
    ALL_APPIDS,
    APPID_LABELS,
    DEFAULT_APPID,
    SIGNATURE_LEN,
    build_fsc,
    hex_dump,
    load_template,
    parse_appid,
    spaced_hex,
    validate_vin,
)


APP_DIR = Path(__file__).resolve().parent
CREATOR_LINK = "https://t.me/imkadi"
LEGAL_NOTICE = """Easy FSC E3

Created by: https://t.me/imkadi

Free Use Only:
This app is provided for free. It may not be sold, rented, sublicensed, bundled for paid resale, or used as part of a paid service without the creator's written permission.

Authorized and Lawful Use Only:
Use this app only on systems, vehicles, files, and data that you own or have explicit permission to service. The user is responsible for complying with all applicable laws, contracts, warranties, software licenses, and local regulations.

No Warranty:
This app is provided "as is" without warranties of any kind. The creator is not responsible for damage, loss, misuse, legal issues, warranty problems, or other consequences caused by use of this app.

No Official Affiliation:
This app is an independent utility and is not endorsed by, sponsored by, or affiliated with any vehicle manufacturer, dealer, software vendor, or other third party.
"""


class EasyFscApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Easy FSC E3")
        self.geometry("860x650")
        self.minsize(760, 560)

        self.template_path: Path | None = None
        self.output_dir = APP_DIR / "output"
        self.last_output_dir: Path | None = None

        self.vin_var = tk.StringVar()
        self.mode_var = tk.StringVar(value="single")
        self.appid_var = tk.StringVar(value=f"{DEFAULT_APPID:04X}")
        self.custom_appid_var = tk.StringVar()
        self.template_var = tk.StringVar(value="Built-in template")
        self.output_var = tk.StringVar(value=str(self.output_dir))
        self.status_var = tk.StringVar(value="Ready")

        self._configure_style()
        self._build_menu()
        self._build_ui()
        self._sync_mode()

    def _configure_style(self) -> None:
        self.configure(bg="#f5f7fb")
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background="#f5f7fb")
        style.configure("Card.TFrame", background="#ffffff", relief="flat")
        style.configure("TLabel", background="#f5f7fb", foreground="#1f2937")
        style.configure("Card.TLabel", background="#ffffff", foreground="#1f2937")
        style.configure("Title.TLabel", font=("Segoe UI", 20, "bold"))
        style.configure("Section.TLabel", font=("Segoe UI", 11, "bold"), background="#ffffff")
        style.configure("Hint.TLabel", font=("Segoe UI", 9), foreground="#64748b", background="#ffffff")
        style.configure("Primary.TButton", font=("Segoe UI", 11, "bold"), padding=(14, 10))
        style.configure("TButton", font=("Segoe UI", 10), padding=(10, 7))
        style.configure("TRadiobutton", background="#ffffff", foreground="#1f2937", font=("Segoe UI", 10))
        style.configure("TCheckbutton", background="#ffffff", foreground="#1f2937")
        style.configure("TCombobox", padding=6)

    def _build_menu(self) -> None:
        menu = tk.Menu(self)
        help_menu = tk.Menu(menu, tearoff=0)
        help_menu.add_command(label="Legal Notice", command=self._show_legal_notice)
        help_menu.add_command(label="About", command=self._show_about)
        menu.add_cascade(label="Help", menu=help_menu)
        self.config(menu=menu)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=18)
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0, 14))
        ttk.Label(header, text="Easy FSC E3", style="Title.TLabel").pack(side="left")
        ttk.Button(header, text="Open Output Folder", command=self._open_output_folder).pack(side="right")

        main = ttk.Frame(outer)
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=0)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)

        left = ttk.Frame(main, style="Card.TFrame", padding=18)
        left.grid(row=0, column=0, sticky="ns", padx=(0, 14))
        right = ttk.Frame(main, style="Card.TFrame", padding=18)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        self._build_controls(left)
        self._build_results(right)

        footer = ttk.Frame(outer)
        footer.pack(fill="x", pady=(12, 0))
        ttk.Label(footer, textvariable=self.status_var).pack(side="left")
        ttk.Label(
            footer,
            text=f"Created by {CREATOR_LINK} | Free use only, not for resale",
            foreground="#475569",
        ).pack(side="right")

    def _build_controls(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="1. Enter VIN", style="Section.TLabel").pack(anchor="w")
        vin = ttk.Entry(parent, textvariable=self.vin_var, font=("Consolas", 18, "bold"), width=12)
        vin.pack(fill="x", pady=(6, 4))
        vin.bind("<KeyRelease>", self._format_vin)
        ttk.Label(parent, text="Use exactly 7 letters or digits.", style="Hint.TLabel").pack(anchor="w")

        ttk.Separator(parent).pack(fill="x", pady=16)

        ttk.Label(parent, text="2. Pick App ID", style="Section.TLabel").pack(anchor="w")
        modes = ttk.Frame(parent, style="Card.TFrame")
        modes.pack(fill="x", pady=(8, 6))
        ttk.Radiobutton(
            modes,
            text="One App ID",
            value="single",
            variable=self.mode_var,
            command=self._sync_mode,
        ).pack(anchor="w", pady=2)
        ttk.Radiobutton(
            modes,
            text="All App IDs",
            value="all",
            variable=self.mode_var,
            command=self._sync_mode,
        ).pack(anchor="w", pady=2)
        ttk.Radiobutton(
            modes,
            text="ZIP with all App IDs",
            value="zip",
            variable=self.mode_var,
            command=self._sync_mode,
        ).pack(anchor="w", pady=2)

        self.appid_combo = ttk.Combobox(
            parent,
            textvariable=self.appid_var,
            values=[APPID_LABELS.get(appid, f"{appid:04X}") for appid in ALL_APPIDS],
            state="readonly",
            width=22,
        )
        self.appid_combo.pack(fill="x", pady=(8, 4))
        self.appid_combo.set(APPID_LABELS[DEFAULT_APPID])

        custom_row = ttk.Frame(parent, style="Card.TFrame")
        custom_row.pack(fill="x", pady=(4, 0))
        ttk.Label(custom_row, text="Custom:", style="Card.TLabel").pack(side="left")
        self.custom_entry = ttk.Entry(custom_row, textvariable=self.custom_appid_var, width=10)
        self.custom_entry.pack(side="left", padx=(8, 0))

        ttk.Separator(parent).pack(fill="x", pady=16)

        ttk.Label(parent, text="3. Choose Files", style="Section.TLabel").pack(anchor="w")
        ttk.Button(parent, text="Use Custom Template...", command=self._choose_template).pack(fill="x", pady=(8, 4))
        ttk.Label(parent, textvariable=self.template_var, style="Hint.TLabel", wraplength=290).pack(anchor="w")
        ttk.Button(parent, text="Choose Output Folder...", command=self._choose_output_dir).pack(fill="x", pady=(12, 4))
        ttk.Label(parent, textvariable=self.output_var, style="Hint.TLabel", wraplength=290).pack(anchor="w")

        ttk.Separator(parent).pack(fill="x", pady=16)

        ttk.Button(parent, text="Generate FSC", style="Primary.TButton", command=self.generate).pack(fill="x")
        ttk.Button(parent, text="Legal Notice", command=self._show_legal_notice).pack(fill="x", pady=(8, 0))
        ttk.Button(parent, text="Clear", command=self._clear).pack(fill="x", pady=(8, 0))

    def _build_results(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Result", style="Section.TLabel").grid(row=0, column=0, sticky="w")

        notebook = ttk.Notebook(parent)
        notebook.grid(row=1, column=0, sticky="nsew", pady=(8, 0))

        self.log_text = self._text_tab(notebook, "Log", wrap="word")
        self.hex_text = self._text_tab(notebook, "Hex Preview", wrap="none")

    def _text_tab(self, notebook: ttk.Notebook, title: str, wrap: str) -> tk.Text:
        frame = ttk.Frame(notebook, padding=8)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        text = tk.Text(
            frame,
            wrap=wrap,
            font=("Consolas", 10),
            bg="#0f172a",
            fg="#e5e7eb",
            insertbackground="#e5e7eb",
            relief="flat",
            padx=10,
            pady=10,
        )
        yscroll = ttk.Scrollbar(frame, command=text.yview)
        text.configure(yscrollcommand=yscroll.set)
        text.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        notebook.add(frame, text=title)
        return text

    def _format_vin(self, _event: tk.Event | None = None) -> None:
        value = "".join(ch for ch in self.vin_var.get().upper() if ch.isalnum())[:7]
        if value != self.vin_var.get():
            self.vin_var.set(value)

    def _sync_mode(self) -> None:
        state = "normal" if self.mode_var.get() == "single" else "disabled"
        self.appid_combo.configure(state="readonly" if state == "normal" else "disabled")
        self.custom_entry.configure(state=state)

    def _choose_template(self) -> None:
        path = filedialog.askopenfilename(
            title="Choose FSC template",
            filetypes=(("FSC or binary files", "*.fsc *.bin *.dat"), ("All files", "*.*")),
        )
        if not path:
            return
        self.template_path = Path(path)
        self.template_var.set(str(self.template_path))

    def _choose_output_dir(self) -> None:
        path = filedialog.askdirectory(title="Choose output folder")
        if not path:
            return
        self.output_dir = Path(path)
        self.output_var.set(str(self.output_dir))

    def _selected_appid(self) -> int:
        custom = self.custom_appid_var.get().strip()
        if custom:
            return parse_appid(custom)
        selected = self.appid_var.get().split("-", 1)[0].strip()
        return parse_appid(selected)

    def generate(self) -> None:
        try:
            vin = validate_vin(self.vin_var.get())
            template = load_template(self.template_path)
            self.output_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            messagebox.showerror("Check Input", str(exc))
            return

        vin_text = vin.decode("ascii")
        mode = self.mode_var.get()

        try:
            if mode == "single":
                appid = self._selected_appid()
                result = build_fsc(template, vin, appid)
                output_path = self.output_dir / f"FSC_{vin_text}_{appid:04x}.fsc"
                output_path.write_bytes(result.data)
                self.last_output_dir = self.output_dir
                self._show_single_result(output_path, appid, result)
            elif mode == "zip":
                zip_path = self.output_dir / f"FSC_{vin_text}_all.zip"
                first = self._write_zip(zip_path, template, vin, vin_text)
                self.last_output_dir = self.output_dir
                self._show_batch_result(zip_path, len(ALL_APPIDS), first)
            else:
                batch_dir = self.output_dir / vin_text
                batch_dir.mkdir(parents=True, exist_ok=True)
                first = self._write_all_files(batch_dir, template, vin, vin_text)
                self.last_output_dir = batch_dir
                self._show_batch_result(batch_dir, len(ALL_APPIDS), first)
        except Exception as exc:
            messagebox.showerror("Generation Failed", str(exc))
            self.status_var.set("Generation failed")
            return

        self.status_var.set("Done")

    def _write_all_files(self, folder: Path, template: bytearray, vin: bytes, vin_text: str):
        first = None
        for appid in ALL_APPIDS:
            result = build_fsc(template, vin, appid)
            (folder / f"FSC_{vin_text}_{appid:04x}.fsc").write_bytes(result.data)
            first = first or (appid, result)
        return first

    def _write_zip(self, zip_path: Path, template: bytearray, vin: bytes, vin_text: str):
        first = None
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for appid in ALL_APPIDS:
                result = build_fsc(template, vin, appid)
                archive.writestr(f"FSC_{vin_text}_{appid:04x}.fsc", result.data)
                first = first or (appid, result)
        return first

    def _show_single_result(self, path: Path, appid: int, result) -> None:
        self._set_log(
            "\n".join(
                [
                    "Generated one FSC file.",
                    "",
                    f"File: {path}",
                    f"Size: {len(result.data)} bytes",
                    f"App ID: 0x{appid:04X}",
                    f"MD5 body: {spaced_hex(result.digest)}",
                    f"RSA quotient q: {result.quotient}",
                    "Weak suffix check: PASS",
                    f"Strict PKCS#1 v1.5: {'PASS' if result.strict_valid else 'FAIL'}",
                ]
            )
        )
        self._set_hex(hex_dump(result.data))
        messagebox.showinfo("FSC Created", f"Saved:\n{path}")

    def _show_batch_result(self, path: Path, count: int, first) -> None:
        appid, result = first
        self._set_log(
            "\n".join(
                [
                    f"Generated {count} FSC files.",
                    "",
                    f"Output: {path}",
                    f"First App ID: 0x{appid:04X}",
                    f"First MD5 body: {spaced_hex(result.digest)}",
                    f"First RSA quotient q: {result.quotient}",
                    "Weak suffix check: PASS",
                    f"Strict PKCS#1 v1.5: {'PASS' if result.strict_valid else 'FAIL'}",
                ]
            )
        )
        self._set_hex(hex_dump(result.data))
        messagebox.showinfo("FSC Created", f"Generated {count} files in:\n{path}")

    def _set_log(self, value: str) -> None:
        self.log_text.delete("1.0", "end")
        self.log_text.insert("1.0", value)

    def _set_hex(self, value: str) -> None:
        self.hex_text.delete("1.0", "end")
        self.hex_text.insert("1.0", value)

    def _open_output_folder(self) -> None:
        folder = self.last_output_dir or self.output_dir
        folder.mkdir(parents=True, exist_ok=True)
        if sys.platform.startswith("win"):
            subprocess.Popen(["explorer", str(folder)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(folder)])
        else:
            opener = shutil.which("xdg-open")
            if opener:
                subprocess.Popen([opener, str(folder)])

    def _show_legal_notice(self) -> None:
        messagebox.showinfo("Legal Notice", LEGAL_NOTICE)

    def _show_about(self) -> None:
        messagebox.showinfo(
            "About Easy FSC E3",
            f"Easy FSC E3\n\nCreated by: {CREATOR_LINK}\nFree use only, not for resale.",
        )

    def _clear(self) -> None:
        self.vin_var.set("")
        self.custom_appid_var.set("")
        self.mode_var.set("single")
        self.appid_combo.set(APPID_LABELS[DEFAULT_APPID])
        self.template_path = None
        self.template_var.set("Built-in template")
        self._set_log("")
        self._set_hex("")
        self._sync_mode()
        self.status_var.set("Ready")


def main() -> int:
    app = EasyFscApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
