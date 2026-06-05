import os
import sys
import logging
import re
import tkinter
from tkinter import ttk, messagebox, filedialog
import customtkinter

from app.models.config import ReportConfig, TableItem
from app.services import config_loader, report_builder
from app.utils.paths import resolve_dynamic_path

logger = logging.getLogger("DocBuilder.TablesWindow")

class TablesWindow(customtkinter.CTkFrame):
    def __init__(self, parent, controller, config: ReportConfig, config_path: str):
        # We call the frame constructor instead of TopLevel
        super().__init__(parent, fg_color="transparent")
        self.config = config
        self.config_path = config_path
        self.controller = controller
        
        self._config_updated_callbacks = []
        self.init_ui()
        self.load_config_data()

    def config_updated_connect(self, callback):
        self._config_updated_callbacks.append(callback)

    def emit_config_updated(self):
        for cb in self._config_updated_callbacks:
            cb()

    def get_accent_theme(self):
        theme_name = getattr(self.config, "accent_color", "blue") or "blue"
        THEME_COLORS = {
            "blue":    {"fg": "#3b82f6", "hover": "#2563eb"},
            "emerald": {"fg": "#10b981", "hover": "#059669"},
            "rose":    {"fg": "#f43f5e", "hover": "#e11d48"},
            "amber":   {"fg": "#f59e0b", "hover": "#d97706"},
            "purple":  {"fg": "#8b5cf6", "hover": "#7c3aed"}
        }
        return THEME_COLORS.get(theme_name.lower(), THEME_COLORS["blue"])

    def refresh_theme_colors(self):
        accent = self.get_accent_theme()
        # Update colors of primary UI buttons
        self.lbl_title.configure(text_color=accent["fg"])
        self.btn_save.configure(fg_color="#333333", hover_color="#444444")
        self.btn_apply.configure(fg_color=accent["fg"], hover_color=accent["hover"])
        self.btn_launch.configure(fg_color=accent["fg"], hover_color=accent["hover"])
        if hasattr(self, "btn_grab"):
            self.btn_grab.configure(fg_color=accent["fg"], hover_color=accent["hover"])

    def init_ui(self):
        # Configure grid layout: row 0 is navigation, row 1 is main area
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0, minsize=240)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)

        accent = self.get_accent_theme()

        # 0. Navigation Header Bar (Row 0)
        header_bar = customtkinter.CTkFrame(self, fg_color="transparent")
        header_bar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=(4, 0))
        
        btn_back = customtkinter.CTkButton(
            header_bar, text="← Назад в меню", width=120, height=28, 
            font=("Segoe UI", 11, "bold"), fg_color="#333333", hover_color="#444444",
            command=self.go_back
        )
        btn_back.pack(side="left", padx=(0, 12))

        self.lbl_title = customtkinter.CTkLabel(
            header_bar, text="ВЕРСТКА ТАБЛИЦ", font=("Segoe UI", 14, "bold"),
            text_color=accent["fg"]
        )
        self.lbl_title.pack(side="left")

        # 1. Main Left/Middle Area Frame (Row 1)
        middle_widget = customtkinter.CTkFrame(self, fg_color="transparent")
        middle_widget.grid(row=1, column=0, sticky="nsew", padx=12, pady=12)
        middle_widget.grid_columnconfigure(0, weight=1)
        middle_widget.grid_rowconfigure(1, weight=1) # Treeview is row 1
        middle_widget.grid_rowconfigure(2, weight=0) # Editor is row 2
        middle_widget.grid_rowconfigure(3, weight=0) # Paths is row 3

        # Toolbar layout (Row 0 inside middle)
        toolbar = customtkinter.CTkFrame(middle_widget, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        self.btn_save = customtkinter.CTkButton(
            toolbar, text="Сохранить изменения", width=140, height=28, 
            font=("Segoe UI", 11, "bold"), fg_color="#333333", hover_color="#444444", command=self.save_data
        )
        self.btn_save.pack(side="left", padx=(0, 6))

        self.btn_add = customtkinter.CTkButton(
            toolbar, text="Добавить строку", width=120, height=28, 
            font=("Segoe UI", 11), command=self.add_row
        )
        self.btn_add.pack(side="left", padx=(0, 6))

        self.btn_grab = customtkinter.CTkButton(
            toolbar, text="Захватить из Excel", width=140, height=28, 
            font=("Segoe UI", 11, "bold"), fg_color=accent["fg"], hover_color=accent["hover"],
            command=self.grab_from_excel
        )
        self.btn_grab.pack(side="left", padx=(0, 6))

        self.btn_del = customtkinter.CTkButton(
            toolbar, text="Удалить строку", width=120, height=28, 
            font=("Segoe UI", 11), command=self.delete_row
        )
        self.btn_del.pack(side="left", padx=(0, 6))

        self.btn_view = customtkinter.CTkButton(
            toolbar, text="Открыть Excel", width=120, height=28, 
            font=("Segoe UI", 11), command=self.view_excel
        )
        self.btn_view.pack(side="left", padx=(0, 6))

        # Setup Treeview for grid (Row 1)
        grid_container = customtkinter.CTkFrame(middle_widget, fg_color="transparent")
        grid_container.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        grid_container.grid_columnconfigure(0, weight=1)
        grid_container.grid_rowconfigure(0, weight=1)

        # Style Treeview
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", 
                        background="#18181b", 
                        foreground="#f4f4f5", 
                        fieldbackground="#18181b", 
                        rowheight=26,
                        bordercolor="#27272a",
                        borderwidth=1)
        style.map("Treeview", background=[("selected", "#27272a")], foreground=[("selected", "#3b82f6")])
        style.configure("Treeview.Heading", 
                        background="#27272a", 
                        foreground="#ffffff", 
                        relief="flat",
                        font=("Segoe UI", 10, "bold"))
        style.map("Treeview.Heading", background=[("active", "#3f3f46")])

        self.table_widget = ttk.Treeview(
            grid_container, 
            columns=("Tag", "Link", "Sheet", "RangeA", "RangeB", "Use", "Header"),
            show="headings",
            selectmode="browse"
        )
        self.table_widget.grid(row=0, column=0, sticky="nsew")

        # Scrollbars
        scrollbar_v = customtkinter.CTkScrollbar(grid_container, orientation="vertical", command=self.table_widget.yview)
        scrollbar_v.grid(row=0, column=1, sticky="ns")
        self.table_widget.configure(yscrollcommand=scrollbar_v.set)

        self.table_widget.heading("Tag", text="Tag (Тег)")
        self.table_widget.heading("Link", text="Link (Ссылка)")
        self.table_widget.heading("Sheet", text="SheetId (Лист)")
        self.table_widget.heading("RangeA", text="RangeA (Яч. А)")
        self.table_widget.heading("RangeB", text="RangeB (Яч. Б)")
        self.table_widget.heading("Use", text="Use")
        self.table_widget.heading("Header", text="Header")

        self.table_widget.column("Tag", width=140, anchor="w")
        self.table_widget.column("Link", width=250, anchor="w")
        self.table_widget.column("Sheet", width=100, anchor="w")
        self.table_widget.column("RangeA", width=80, anchor="center")
        self.table_widget.column("RangeB", width=80, anchor="center")
        self.table_widget.column("Use", width=60, anchor="center")
        self.table_widget.column("Header", width=60, anchor="center")

        self.table_widget.bind("<<TreeviewSelect>>", self.row_selected)

        # 2. Row Editor Frame (Row 2) - inputs to modify selected row
        editor_frame = customtkinter.CTkFrame(middle_widget, fg_color="#18181b", border_width=1, border_color="#27272a", corner_radius=6)
        editor_frame.grid(row=2, column=0, sticky="ew", pady=(0, 10), padx=2)
        
        # Row 1 of editor: inputs
        customtkinter.CTkLabel(editor_frame, text="Tag:", font=("Segoe UI", 11)).grid(row=0, column=0, padx=8, pady=6, sticky="e")
        self.entry_tag = customtkinter.CTkEntry(editor_frame, width=120, font=("Segoe UI", 11))
        self.entry_tag.grid(row=0, column=1, padx=4, pady=6, sticky="w")

        customtkinter.CTkLabel(editor_frame, text="Link:", font=("Segoe UI", 11)).grid(row=0, column=2, padx=8, pady=6, sticky="e")
        self.entry_link = customtkinter.CTkEntry(editor_frame, width=220, font=("Segoe UI", 11))
        self.entry_link.grid(row=0, column=3, padx=4, pady=6, sticky="w")
        self.btn_browse_excel = customtkinter.CTkButton(editor_frame, text="...", width=28, height=28, command=self.browse_excel_file)
        self.btn_browse_excel.grid(row=0, column=4, padx=2, pady=6, sticky="w")

        customtkinter.CTkLabel(editor_frame, text="Лист:", font=("Segoe UI", 11)).grid(row=0, column=5, padx=8, pady=6, sticky="e")
        self.entry_sheet = customtkinter.CTkEntry(editor_frame, width=100, font=("Segoe UI", 11))
        self.entry_sheet.grid(row=0, column=6, padx=4, pady=6, sticky="w")

        # Row 2 of editor: inputs
        customtkinter.CTkLabel(editor_frame, text="Яч. А:", font=("Segoe UI", 11)).grid(row=1, column=0, padx=8, pady=6, sticky="e")
        self.entry_range_a = customtkinter.CTkEntry(editor_frame, width=70, font=("Segoe UI", 11))
        self.entry_range_a.grid(row=1, column=1, padx=4, pady=6, sticky="w")

        customtkinter.CTkLabel(editor_frame, text="Яч. Б:", font=("Segoe UI", 11)).grid(row=1, column=2, padx=8, pady=6, sticky="e")
        self.entry_range_b = customtkinter.CTkEntry(editor_frame, width=70, font=("Segoe UI", 11))
        self.entry_range_b.grid(row=1, column=3, padx=4, pady=6, sticky="w")

        self.val_use = tkinter.BooleanVar(value=True)
        self.chk_use = customtkinter.CTkCheckBox(editor_frame, text="Использовать", variable=self.val_use, font=("Segoe UI", 11))
        self.chk_use.grid(row=1, column=4, columnspan=2, padx=8, pady=6, sticky="w")

        self.val_header = tkinter.BooleanVar(value=False)
        self.chk_header = customtkinter.CTkCheckBox(editor_frame, text="Заголовок", variable=self.val_header, font=("Segoe UI", 11))
        self.chk_header.grid(row=1, column=6, padx=8, pady=6, sticky="w")

        self.btn_apply = customtkinter.CTkButton(
            editor_frame, text="Применить", width=100, height=28, 
            font=("Segoe UI", 11, "bold"), fg_color=accent["fg"], hover_color=accent["hover"], command=self.apply_row_changes
        )
        self.btn_apply.grid(row=0, column=7, rowspan=2, padx=12, pady=6, sticky="ns")

        # Bottom Paths Panel (Row 3)
        bottom_panel = customtkinter.CTkFrame(middle_widget, fg_color="transparent")
        bottom_panel.grid(row=3, column=0, sticky="ew", pady=5)
        bottom_panel.grid_columnconfigure(0, weight=1)

        word_row = customtkinter.CTkFrame(bottom_panel, fg_color="transparent")
        word_row.grid(row=0, column=0, sticky="ew")
        word_row.grid_columnconfigure(1, weight=1)

        lbl_word = customtkinter.CTkLabel(word_row, text="Файл верстки:", font=("Segoe UI", 11, "bold"))
        lbl_word.grid(row=0, column=0, padx=(0, 8), pady=4)

        self.edit_word_path = customtkinter.CTkEntry(word_row, font=("Segoe UI", 11))
        self.edit_word_path.grid(row=0, column=1, sticky="ew", padx=(0, 6), pady=4)

        self.btn_word_browse = customtkinter.CTkButton(word_row, text="...", width=32, height=28, command=self.browse_word_file)
        self.btn_word_browse.grid(row=0, column=2, padx=(0, 6), pady=4)

        self.btn_word_open = customtkinter.CTkButton(word_row, text="ОТКРЫТЬ", width=80, height=28, command=self.open_word_file)
        self.btn_word_open.grid(row=0, column=3, pady=4)

        # Launch Button
        self.btn_launch = customtkinter.CTkButton(
            bottom_panel, text="ЗАПУСК", width=140, height=34,
            font=("Segoe UI", 14, "bold"), fg_color=accent["fg"], hover_color=accent["hover"],
            command=self.run_generation
        )
        self.btn_launch.grid(row=0, column=1, padx=(12, 0), sticky="ns")

        # 3. Right Preview panel
        preview_panel = customtkinter.CTkFrame(self, width=240, fg_color="transparent")
        preview_panel.grid(row=1, column=1, sticky="nsew", padx=(6, 12), pady=12)
        preview_panel.grid_propagate(False)
        preview_panel.grid_columnconfigure(0, weight=1)
        preview_panel.grid_rowconfigure(1, weight=1)

        lbl_preview = customtkinter.CTkLabel(preview_panel, text="Предпросмотр", font=("Segoe UI", 12, "bold"), text_color="#888888")
        lbl_preview.grid(row=0, column=0, sticky="w", pady=(0, 6))

        self.preview_box = customtkinter.CTkFrame(preview_panel, fg_color="#151515", border_width=1, border_color="#2d2d2d")
        self.preview_box.grid(row=1, column=0, sticky="nsew")

    def go_back(self):
        # Save config changes before returning
        self.save_data(show_msg=False)
        # Main window show_dashboard
        if hasattr(self.controller, "show_dashboard"):
            self.controller.show_dashboard()

    def copy_text_to_clipboard(self, text):
        if sys.platform == "win32":
            try:
                import win32clipboard
                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardText(text)
                win32clipboard.CloseClipboard()
                return
            except Exception as e:
                logger.warning(f"win32clipboard failed: {e}")

        # Fallback to standard Tkinter Clipboard
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
            self.update()
        except Exception as e:
            logger.error(f"Tkinter clipboard failed: {e}")

    def grab_from_excel(self):
        import re
        if sys.platform != "win32":
            messagebox.showwarning(
                "Не поддерживается", 
                "Захват данных из Excel поддерживается только на ОС Windows с установленным Microsoft Excel.", 
                parent=self
            )
            return

        try:
            import win32com.client
            # Try connecting to active Excel
            try:
                excel = win32com.client.GetActiveObject("Excel.Application")
            except Exception:
                messagebox.showwarning(
                    "Excel не запущен", 
                    "Пожалуйста, запустите Microsoft Excel, откройте нужную книгу и выделите ячейки для копирования.", 
                    parent=self
                )
                return

            active_chart = excel.ActiveChart
            if active_chart is not None:
                messagebox.showwarning(
                    "Выбран график", 
                    "Вы выделили график в Excel. Для настройки графиков перейдите в меню 'Верстка диаграмм'.", 
                    parent=self
                )
                return

            wb = excel.ActiveWorkbook
            ws = excel.ActiveSheet
            sel = excel.Selection

            if wb is None or ws is None or sel is None:
                messagebox.showwarning("Ошибка выбора", "Не удалось обнаружить активную книгу, лист или ячейки в Excel.", parent=self)
                return

            if not hasattr(sel, "Address"):
                messagebox.showwarning("Ошибка выбора", "Выделенный объект в Excel не является диапазоном ячеек.", parent=self)
                return

            # Extract data
            excel_path = wb.FullName
            sheet_name = ws.Name
            address = sel.Address(RowAbsolute=False, ColumnAbsolute=False)

            if ":" in address:
                range_a, range_b = address.split(":")
            else:
                range_a = address
                range_b = ""

            # Try to resolve relative path if config_path is loaded
            if self.config_path:
                try:
                    rel = os.path.relpath(excel_path, os.path.dirname(self.config_path))
                    if not rel.startswith(".."):
                        excel_path = rel
                except ValueError:
                    pass

            # Generate unique tag TableTag_N
            max_num = 0
            for child in self.table_widget.get_children():
                tag_val = self.table_widget.item(child)["values"][0]
                num_match = re.search(r'\d+', tag_val)
                if num_match:
                    max_num = max(max_num, int(num_match.group(0)))
            new_tag = f"<TableTag_{max_num + 1}>"

            # Insert into Treeview
            new_row_id = self.table_widget.insert("", "end", values=(
                new_tag,
                excel_path,
                sheet_name,
                range_a,
                range_b,
                "Да",
                "Нет"
            ))

            # Select and refresh editor
            self.table_widget.selection_set(new_row_id)
            self.table_widget.see(new_row_id)
            self.row_selected()

            # Copy tag to clipboard
            self.copy_text_to_clipboard(new_tag)

            messagebox.showinfo(
                "Успешный захват",
                f"Успешно импортирован диапазон {range_a}:{range_b} на листе '{sheet_name}'.\n\n"
                f"Создан новый тег: {new_tag} (скопирован в буфер обмена!).\n"
                f"Вставьте тег (Ctrl+V) в нужное место в Word.",
                parent=self
            )

        except Exception as e:
            messagebox.showerror("Ошибка импорта", f"Произошел сбой при получении выделения:\n{e}", parent=self)

    def load_config_data(self):
        self.refresh_theme_colors()
        self.edit_word_path.delete(0, "end")
        self.edit_word_path.insert(0, self.config.output_path)

        # Clear treeview
        for item in self.table_widget.get_children():
            self.table_widget.delete(item)

        for item in self.config.tables:
            self.table_widget.insert("", "end", values=(
                item.tag,
                item.excel_path,
                item.sheet,
                item.range_a,
                item.range_b,
                "Да" if item.use else "Нет",
                "Да" if item.header else "Нет"
            ))

    def row_selected(self, event=None):
        selection = self.table_widget.selection()
        if not selection:
            return
        
        item = self.table_widget.item(selection[0])
        values = item["values"]
        
        self.entry_tag.delete(0, "end")
        self.entry_tag.insert(0, values[0])

        self.entry_link.delete(0, "end")
        self.entry_link.insert(0, values[1])

        self.entry_sheet.delete(0, "end")
        self.entry_sheet.insert(0, values[2])

        self.entry_range_a.delete(0, "end")
        self.entry_range_a.insert(0, values[3])

        self.entry_range_b.delete(0, "end")
        self.entry_range_b.insert(0, values[4])

        self.val_use.set(values[5] == "Да")
        self.chk_use.select() if values[5] == "Да" else self.chk_use.deselect()
        
        self.val_header.set(values[6] == "Да")
        self.chk_header.select() if values[6] == "Да" else self.chk_header.deselect()

    def apply_row_changes(self):
        selection = self.table_widget.selection()
        if not selection:
            messagebox.showwarning("Предупреждение", "Пожалуйста, выберите строку для редактирования.", parent=self)
            return

        tag = self.entry_tag.get().strip()
        link = self.entry_link.get().strip()
        sheet = self.entry_sheet.get().strip()
        range_a = self.entry_range_a.get().strip()
        range_b = self.entry_range_b.get().strip()
        use = "Да" if self.val_use.get() else "Нет"
        header = "Да" if self.val_header.get() else "Нет"

        if not tag:
            messagebox.showwarning("Ошибка", "Тег не может быть пустым.", parent=self)
            return

        self.table_widget.item(selection[0], values=(tag, link, sheet, range_a, range_b, use, header))

    def add_row(self):
        new_row_id = self.table_widget.insert("", "end", values=(
            "<TableTag_New>", "", "Sheet1", "A1", "", "Да", "Нет"
        ))
        self.table_widget.selection_set(new_row_id)
        self.table_widget.see(new_row_id)

    def delete_row(self):
        selection = self.table_widget.selection()
        if selection:
            self.table_widget.delete(selection[0])
            self.entry_tag.delete(0, "end")
            self.entry_link.delete(0, "end")
            self.entry_sheet.delete(0, "end")
            self.entry_range_a.delete(0, "end")
            self.entry_range_b.delete(0, "end")
            self.val_use.set(True)
            self.val_header.set(False)
        else:
            messagebox.showwarning("Предупреждение", "Выберите строку для удаления.", parent=self)

    def browse_excel_file(self):
        initial_dir = getattr(self.config, "default_word_dir", "")
        if not initial_dir or not os.path.exists(resolve_dynamic_path(initial_dir, self.config_path)):
            initial_dir = os.path.dirname(self.config_path) if self.config_path else os.getcwd()
        else:
            initial_dir = resolve_dynamic_path(initial_dir, self.config_path)

        file_path = filedialog.askopenfilename(
            title="Выберите файл Excel",
            initialdir=initial_dir,
            filetypes=[("Файлы Excel", "*.xlsx *.xls *.xlsm")],
            parent=self
        )
        if file_path:
            norm_path = os.path.normpath(file_path)
            if self.config_path:
                try:
                    rel = os.path.relpath(norm_path, os.path.dirname(self.config_path))
                    if not rel.startswith(".."):
                        norm_path = rel
                except ValueError:
                    pass
            self.entry_link.delete(0, "end")
            self.entry_link.insert(0, norm_path)

    def view_excel(self):
        selection = self.table_widget.selection()
        if selection:
            values = self.table_widget.item(selection[0])["values"]
            excel_path = str(values[1]).strip()
            if not excel_path:
                messagebox.showwarning("Предупреждение", "В выбранной строке не указан путь к Excel-файлу.", parent=self)
                return

            resolved_path = resolve_dynamic_path(excel_path, self.config_path)
            if os.path.exists(resolved_path):
                logger.info(f"Opening Excel file: {resolved_path}")
                try:
                    if sys.platform == "win32":
                        os.startfile(resolved_path)
                    elif sys.platform == "darwin":
                        import subprocess
                        subprocess.run(["open", resolved_path])
                    else:
                        import subprocess
                        subprocess.run(["xdg-open", resolved_path])
                except Exception as e:
                    messagebox.showerror("Ошибка", f"Не удалось открыть файл:\n{e}", parent=self)
            else:
                messagebox.showerror("Ошибка", f"Файл не существует:\n{resolved_path}", parent=self)
        else:
            messagebox.showwarning("Предупреждение", "Выберите строку с таблицей для просмотра.", parent=self)

    def save_data(self, show_msg: bool = True) -> bool:
        norm = os.path.normpath(self.edit_word_path.get().strip())
        self.config.output_path = norm
        self.config.template_path = norm

        tables = []
        for child in self.table_widget.get_children():
            values = self.table_widget.item(child)["values"]
            tag = str(values[0]).strip()
            link = str(values[1]).strip()
            sheet = str(values[2]).strip()
            range_a = str(values[3]).strip()
            range_b = str(values[4]).strip()
            use = (values[5] == "Да")
            header = (values[6] == "Да")

            if tag:
                tables.append(TableItem(
                    tag=tag,
                    excel_path=link,
                    sheet=sheet,
                    range_a=range_a,
                    range_b=range_b,
                    use=use,
                    header=header
                ))

        self.config.tables = tables
        
        if self.config_path:
            try:
                config_loader.save_config_json(self.config, self.config_path)
                logger.info(f"Configuration saved to {self.config_path}")
                self.emit_config_updated()
                if show_msg:
                    messagebox.showinfo("Сохранено", "Конфигурация успешно сохранена на диск!", parent=self)
                return True
            except Exception as e:
                messagebox.showerror("Ошибка сохранения", f"Не удалось сохранить файл:\n{e}", parent=self)
                return False
        else:
            messagebox.showwarning("Предупреждение", "Файл конфигурации не открыт. Сохраните проект через главное окно.", parent=self)
            return False

    def browse_word_file(self):
        initial_dir = getattr(self.config, "default_word_dir", "")
        if not initial_dir or not os.path.exists(resolve_dynamic_path(initial_dir, self.config_path)):
            initial_dir = os.path.dirname(self.config_path) if self.config_path else os.getcwd()
        else:
            initial_dir = resolve_dynamic_path(initial_dir, self.config_path)

        file_path = filedialog.askopenfilename(
            title="Выберите файл верстки Word",
            initialdir=initial_dir,
            filetypes=[("Документы Word", "*.docx *.docm")],
            parent=self
        )
        if file_path:
            self.edit_word_path.delete(0, "end")
            self.edit_word_path.insert(0, os.path.normpath(file_path))

    def open_word_file(self):
        path = self.edit_word_path.get().strip()
        resolved = resolve_dynamic_path(path, self.config_path)
        if path and os.path.exists(resolved):
            try:
                if sys.platform == "win32":
                    os.startfile(resolved)
                elif sys.platform == "darwin":
                    import subprocess
                    subprocess.run(["open", resolved])
                else:
                    import subprocess
                    subprocess.run(["xdg-open", resolved])
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось открыть файл:\n{e}", parent=self)
        else:
            messagebox.showwarning("Файл не найден", f"Файл не найден по пути:\n{resolved}", parent=self)

    def run_generation(self):
        self.save_data(show_msg=False)
        
        logger.info("Запуск верстки таблиц...")
        self.btn_launch.configure(state="disabled", text="ВЕРСТКА...")
        self.update()

        try:
            errors = report_builder.build_report(
                config=self.config,
                config_path=self.config_path,
                run_tables=True,
                run_charts=False,
                clean_tags=False,
                status_callback=lambda msg: (logger.info(msg), self.update())
            )
            
            if errors:
                err_msg = "\n".join(errors[:10])
                if len(errors) > 10:
                    err_msg += f"\n...и еще {len(errors) - 10} ошибок."
                messagebox.showwarning("Верстка таблиц завершена с ошибками", f"Некоторые таблицы не верстались:\n\n{err_msg}", parent=self)
            else:
                messagebox.showinfo("Успех", f"Верстка таблиц завершена успешно!\nРезультат сохранен в:\n{self.config.output_path}", parent=self)
        except Exception as e:
            messagebox.showerror("Ошибка верстки", f"Процесс завершился сбоем:\n{e}", parent=self)
        finally:
            self.btn_launch.configure(state="normal", text="ЗАПУСК")
            # Update main window if needed
            if hasattr(self.parent_window, "update_ui_from_config"):
                self.parent_window.update_ui_from_config()
