from __future__ import annotations

import shutil
import subprocess
import sys
import tkinter as tk
import zipfile
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from fsc_core import (
    ALL_APPIDS,
    APPID_LABELS,
    APP_VERSION,
    APP_VERSION_NAME,
    FEATURE_GUIDE,
    REMOTE_START_GUIDE,
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
        self.title(f"Easy FSC E3 v{APP_VERSION}")
        self.geometry("1060x760")
        self.minsize(980, 700)

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
        self.mode_hint_var = tk.StringVar()
        self.wizard_step = 0
        self.step_title_var = tk.StringVar()
        self.step_hint_var = tk.StringVar()

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
        style.configure("Step.TFrame", background="#ffffff")
        style.configure("Actions.TFrame", background="#ffffff")
        style.configure("TLabel", background="#f5f7fb", foreground="#1f2937")
        style.configure("Card.TLabel", background="#ffffff", foreground="#1f2937")
        style.configure("Title.TLabel", font=("Segoe UI", 22, "bold"))
        style.configure("Subtitle.TLabel", font=("Segoe UI", 10), foreground="#64748b")
        style.configure("Section.TLabel", font=("Segoe UI", 12, "bold"), background="#ffffff")
        style.configure("Hint.TLabel", font=("Segoe UI", 9), foreground="#64748b", background="#ffffff")
        style.configure("Primary.TButton", font=("Segoe UI", 13, "bold"), padding=(18, 13))
        style.configure("TButton", font=("Segoe UI", 10), padding=(10, 7))
        style.configure("TRadiobutton", background="#ffffff", foreground="#1f2937", font=("Segoe UI", 10))
        style.configure("TCheckbutton", background="#ffffff", foreground="#1f2937")
        style.configure("TCombobox", padding=6)

    def _button(
        self,
        parent,
        text: str,
        command,
        variant: str = "secondary",
        height: int = 38,
    ) -> tk.Button:
        palettes = {
            "primary": ("#2563eb", "#1d4ed8", "#ffffff"),
            "secondary": ("#e2e8f0", "#cbd5e1", "#0f172a"),
            "quiet": ("#ffffff", "#f1f5f9", "#334155"),
            "danger": ("#fee2e2", "#fecaca", "#991b1b"),
        }
        bg, hover, fg = palettes[variant]
        button = tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            activebackground=hover,
            activeforeground=fg,
            relief="flat",
            bd=0,
            cursor="hand2",
            font=("Segoe UI", 11, "bold" if variant == "primary" else "normal"),
            height=1,
            padx=12,
            pady=8,
        )
        button.configure(highlightthickness=1, highlightbackground="#cbd5e1")
        button.bind("<Enter>", lambda _event: button.configure(bg=hover))
        button.bind("<Leave>", lambda _event: button.configure(bg=bg))
        button.configure(width=max(1, height // 4))
        return button

    def _option_button(
        self,
        parent,
        text: str,
        value: str,
        variable: tk.StringVar,
        command=None,
    ) -> tk.Button:
        def _select() -> None:
            variable.set(value)
            if command:
                command()
            self._render_step()

        selected = variable.get() == value
        bg = "#dbeafe" if selected else "#ffffff"
        hover = "#bfdbfe" if selected else "#f1f5f9"
        border = "#2563eb" if selected else "#cbd5e1"
        fg = "#1e3a8a" if selected else "#0f172a"
        button = tk.Button(
            parent,
            text=text,
            command=_select,
            bg=bg,
            fg=fg,
            activebackground=hover,
            activeforeground=fg,
            relief="flat",
            bd=0,
            cursor="hand2",
            font=("Segoe UI", 11, "bold" if selected else "normal"),
            anchor="w",
            padx=14,
            pady=12,
        )
        button.configure(highlightthickness=2, highlightbackground=border)
        button.bind("<Enter>", lambda _event: button.configure(bg=hover))
        button.bind("<Leave>", lambda _event: button.configure(bg=bg))
        return button

    def _build_menu(self) -> None:
        menu = tk.Menu(self)
        help_menu = tk.Menu(menu, tearoff=0)
        help_menu.add_command(label="Feature Guide", command=self._show_feature_guide)
        help_menu.add_command(label="1CR Remote Start Guide", command=self._show_remote_start_guide)
        help_menu.add_command(label="Legal Notice", command=self._show_legal_notice)
        help_menu.add_command(label="About", command=self._show_about)
        menu.add_cascade(label="Help", menu=help_menu)
        self.config(menu=menu)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=18)
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0, 14))
        title_box = ttk.Frame(header)
        title_box.pack(side="left")
        ttk.Label(title_box, text=f"Easy FSC E3 v{APP_VERSION}", style="Title.TLabel").pack(anchor="w")
        ttk.Label(title_box, text=f"{APP_VERSION_NAME} | Same FSC output as original", style="Subtitle.TLabel").pack(anchor="w")
        header_actions = ttk.Frame(header)
        header_actions.pack(side="right")
        self._button(header_actions, "Output Folder", self._open_output_folder, "secondary").pack(side="left", padx=(8, 0))
        self._button(header_actions, "1CR", self._show_remote_start_guide, "quiet").pack(side="left", padx=(8, 0))
        self._button(header_actions, "Guide", self._show_feature_guide, "quiet").pack(side="left", padx=(8, 0))

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
        parent.configure(width=360)
        parent.grid_propagate(False)
        parent.rowconfigure(0, weight=1)
        parent.rowconfigure(1, weight=0)
        parent.columnconfigure(0, weight=1)

        content = ttk.Frame(parent, style="Card.TFrame")
        content.grid(row=0, column=0, sticky="nsew")
        content.rowconfigure(2, weight=1)
        content.columnconfigure(0, weight=1)

        ttk.Label(content, textvariable=self.step_title_var, style="Section.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(content, textvariable=self.step_hint_var, style="Hint.TLabel", wraplength=310).grid(
            row=1, column=0, sticky="ew", pady=(5, 18)
        )
        self.step_body = ttk.Frame(content, style="Card.TFrame")
        self.step_body.grid(row=2, column=0, sticky="nsew")

        actions = ttk.Frame(parent, style="Actions.TFrame", padding=(0, 12, 8, 0))
        actions.grid(row=1, column=0, columnspan=2, sticky="ew")
        actions.columnconfigure((0, 1), weight=1)

        self.back_button = self._button(actions, "Back", self._previous_step, "secondary")
        self.back_button.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.next_button = self._button(actions, "Next", self._next_step, "primary")
        self.next_button.grid(row=0, column=1, sticky="ew", padx=(6, 0))

        secondary = ttk.Frame(actions, style="Actions.TFrame")
        secondary.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        secondary.columnconfigure((0, 1, 2, 3), weight=1)
        self._button(secondary, "Guide", self._show_feature_guide, "quiet").grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self._button(secondary, "1CR", self._show_remote_start_guide, "quiet").grid(row=0, column=1, sticky="ew", padx=4)
        self._button(secondary, "Legal", self._show_legal_notice, "quiet").grid(row=0, column=2, sticky="ew", padx=4)
        self._button(secondary, "Clear", self._clear, "danger").grid(row=0, column=3, sticky="ew", padx=(4, 0))
        self._render_step()

    def _clear_step(self) -> None:
        for child in self.step_body.winfo_children():
            child.destroy()

    def _render_step(self) -> None:
        self._clear_step()
        renderers = (
            self._render_vin_step,
            self._render_mode_step,
            self._render_files_step,
            self._render_review_step,
        )
        self.wizard_step = max(0, min(self.wizard_step, len(renderers) - 1))
        renderers[self.wizard_step]()
        back_disabled = self.wizard_step == 0
        self.back_button.configure(state="disabled" if back_disabled else "normal")
        self.back_button.configure(bg="#f1f5f9" if back_disabled else "#e2e8f0")
        self.next_button.configure(text="Generate FSC Files" if self.wizard_step == len(renderers) - 1 else "Next")

    def _render_vin_step(self) -> None:
        self.step_title_var.set("1. Enter VIN")
        self.step_hint_var.set("Use exactly 7 letters or digits. The app keeps the VIN exactly as typed, matching the original script.")
        vin = ttk.Entry(self.step_body, textvariable=self.vin_var, font=("Consolas", 28, "bold"), width=12, justify="center")
        vin.pack(fill="x", pady=(18, 8), ipady=8)
        vin.bind("<KeyRelease>", self._format_vin)
        vin.focus_set()
        ttk.Label(self.step_body, text="Example: TEST123", style="Hint.TLabel").pack(anchor="w")

    def _render_mode_step(self) -> None:
        self.step_title_var.set("2. Choose Output")
        self.step_hint_var.set("Pick one file, a folder with all original App IDs, or a ZIP.")
        for text, value in (
            ("One FSC file", "single"),
            ("Folder with all 21 FSC files", "all"),
            ("ZIP with all 21 FSC files", "zip"),
        ):
            self._option_button(self.step_body, text, value, self.mode_var, self._sync_mode).pack(
                fill="x", pady=5
            )
        ttk.Label(self.step_body, textvariable=self.mode_hint_var, style="Hint.TLabel", wraplength=310).pack(
            anchor="w", pady=(10, 16)
        )
        ttk.Label(self.step_body, text="App ID for one-file mode", style="Hint.TLabel").pack(anchor="w")
        self.appid_combo = ttk.Combobox(
            self.step_body,
            textvariable=self.appid_var,
            values=[APPID_LABELS.get(appid, f"{appid:04X}") for appid in ALL_APPIDS],
            state="readonly",
            width=24,
        )
        self.appid_combo.pack(fill="x", pady=(7, 4))
        if not self.appid_var.get() or self.appid_var.get() == f"{DEFAULT_APPID:04X}":
            self.appid_combo.set(APPID_LABELS[DEFAULT_APPID])
        custom_row = ttk.Frame(self.step_body, style="Card.TFrame")
        custom_row.pack(fill="x", pady=(6, 0))
        ttk.Label(custom_row, text="Custom App ID:", style="Card.TLabel").pack(side="left")
        self.custom_entry = ttk.Entry(custom_row, textvariable=self.custom_appid_var, width=10)
        self.custom_entry.pack(side="left", padx=(8, 0))
        self._sync_mode()

    def _render_files_step(self) -> None:
        self.step_title_var.set("3. Files and Folder")
        self.step_hint_var.set("The built-in template is already selected. Choose an output folder if you want a different location.")
        self._button(self.step_body, "Optional Custom Template", self._choose_template, "secondary").pack(
            fill="x", pady=(14, 5)
        )
        ttk.Label(self.step_body, textvariable=self.template_var, style="Hint.TLabel", wraplength=310).pack(anchor="w")
        self._button(self.step_body, "Choose Output Folder...", self._choose_output_dir, "secondary").pack(
            fill="x", pady=(18, 5)
        )
        ttk.Label(self.step_body, textvariable=self.output_var, style="Hint.TLabel", wraplength=310).pack(anchor="w")

    def _render_review_step(self) -> None:
        self.step_title_var.set("4. Review")
        self.step_hint_var.set("Check the settings, then generate.")
        mode_names = {
            "single": "One FSC file",
            "all": "Folder with all 21 FSC files",
            "zip": "ZIP with all 21 FSC files",
        }
        lines = [
            f"VIN: {self.vin_var.get().strip() or '(missing)'}",
            f"Output: {mode_names.get(self.mode_var.get(), self.mode_var.get())}",
            f"Template: {self.template_var.get()}",
            f"Folder: {self.output_var.get()}",
        ]
        if self.mode_var.get() == "single":
            lines.insert(2, f"App ID: {self.custom_appid_var.get().strip() or self.appid_var.get()}")
        box = tk.Text(
            self.step_body,
            height=9,
            wrap="word",
            font=("Consolas", 10),
            bg="#0f172a",
            fg="#e5e7eb",
            relief="flat",
            padx=10,
            pady=10,
        )
        box.pack(fill="both", expand=True, pady=(14, 0))
        box.insert("1.0", "\n".join(lines))
        box.configure(state="disabled")

    def _next_step(self) -> None:
        if self.wizard_step == 0:
            try:
                validate_vin(self.vin_var.get())
            except Exception as exc:
                messagebox.showerror("Check VIN", str(exc))
                return
        if self.wizard_step >= 3:
            self.generate()
            return
        self.wizard_step += 1
        self._render_step()

    def _previous_step(self) -> None:
        self.wizard_step -= 1
        self._render_step()

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
        value = "".join(ch for ch in self.vin_var.get() if ch.isalnum())[:7]
        if value != self.vin_var.get():
            self.vin_var.set(value)

    def _sync_mode(self) -> None:
        mode = self.mode_var.get()
        state = "normal" if mode == "single" else "disabled"
        if hasattr(self, "appid_combo") and self.appid_combo.winfo_exists():
            self.appid_combo.configure(state="readonly" if state == "normal" else "disabled")
        if hasattr(self, "custom_entry") and self.custom_entry.winfo_exists():
            self.custom_entry.configure(state=state)
        hints = {
            "single": "Creates one .fsc file using the selected App ID.",
            "all": "Creates a VIN folder containing the original 21 App IDs.",
            "zip": "Creates one ZIP containing the original 21 App IDs.",
        }
        self.mode_hint_var.set(hints.get(mode, ""))

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
        label = self._fsc_label

        try:
            if mode == "single":
                appid = self._selected_appid()
                result = build_fsc(template, vin, appid)
                output_path = self.output_dir / f"FSC_{vin_text}_{label(appid)}.fsc"
                output_path.write_bytes(result.data)
                self.last_output_dir = self.output_dir
                self._show_single_result(output_path, appid, result)
            elif mode == "zip":
                zip_path = self.output_dir / f"FSC_{vin_text}_{datetime.now().strftime('%d%m%Y_%H%M%S')}.zip"
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

    @staticmethod
    def _fsc_label(appid: int) -> str:
        return f"{appid:04X}0001"

    def _write_all_files(self, folder: Path, template: bytearray, vin: bytes, vin_text: str):
        first = None
        for appid in ALL_APPIDS:
            result = build_fsc(template, vin, appid)
            (folder / f"FSC_{vin_text}_{self._fsc_label(appid)}.fsc").write_bytes(result.data)
            first = first or (appid, result)
        return first

    def _write_zip(self, zip_path: Path, template: bytearray, vin: bytes, vin_text: str):
        first = None
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for appid in ALL_APPIDS:
                result = build_fsc(template, vin, appid)
                archive.writestr(f"FSC_{vin_text}_{self._fsc_label(appid)}.fsc", result.data)
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

    def _show_feature_guide(self) -> None:
        self._show_text_window("Feature Guide", FEATURE_GUIDE)

    def _show_remote_start_guide(self) -> None:
        self._show_text_window("1CR Remote Start Guide", REMOTE_START_GUIDE)

    def _show_text_window(self, title: str, content: str) -> None:
        top = tk.Toplevel(self)
        top.title(f"{title} - Easy FSC E3 v{APP_VERSION}")
        top.geometry("760x620")
        top.minsize(680, 480)

        frame = ttk.Frame(top, padding=12)
        frame.pack(fill="both", expand=True)
        text = tk.Text(
            frame,
            wrap="word",
            font=("Consolas", 10),
            bg="#0f172a",
            fg="#e5e7eb",
            insertbackground="#e5e7eb",
            relief="flat",
            padx=10,
            pady=10,
        )
        scroll = ttk.Scrollbar(frame, command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        text.insert("1.0", content)
        text.configure(state="disabled")

    def _show_about(self) -> None:
        messagebox.showinfo(
            "About Easy FSC E3",
            f"Easy FSC E3 v{APP_VERSION}\n{APP_VERSION_NAME}\n\nCreated by: {CREATOR_LINK}\nFree use only, not for resale.",
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
