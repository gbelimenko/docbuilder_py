import os
import sys
import logging
import re
import tkinter
from tkinter import ttk, messagebox, filedialog
import customtkinter

from app.models.config import ReportConfig, ChartItem
from app.services import config_loader, report_builder
from app.utils.paths import resolve_dynamic_path

logger = logging.getLogger("DocBuilder.ChartsWindow")

class ChartsWindow(customtkinter.CTkFrame):
    def __init__(self, parent, controller, config: ReportConfig, config_path: str):
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

    def get_theme(self) -> dict:
        if hasattr(self.controller, "get_theme"):
            return self.controller.get_theme()
        from app.utils.themes import buildTheme
        return buildTheme("dark", "#3B82F6")

    def refresh_theme_colors(self):
        theme = self.get_theme()
        colors = theme["colors"]
        
        self.configure(fg_color=colors["bg"])
        self.lbl_title.configure(text_color=colors["primary"])
        
        # Primary Action Buttons
        self.btn_grab.configure(fg_color=colors["primary"], hover_color=colors["primaryHover"], text_color="#ffffff")
        self.btn_apply.configure(fg_color=colors["primary"], hover_color=colors["primaryHover"], text_color="#ffffff")
        self.btn_launch.configure(fg_color=colors["primary"], hover_color=colors["primaryHover"], text_color="#ffffff")
        self.btn_word_open.configure(
            fg_color=colors["success"],
            hover_color=colors["primaryHover"],
            text_color="#ffffff"
        )
        self.btn_load_prev.configure(
            fg_color=colors["surface2"],
            hover_color=colors["border"],
            text_color=colors["text"]
        )

        # Standard Buttons
        for btn in [self.btn_save, self.btn_add, self.btn_del, self.btn_view, self.btn_word_browse, self.btn_browse_excel]:
            btn.configure(
                fg_color=colors["surface2"], 
                hover_color=colors["border"],
                text_color=colors["text"]
            )
            
        # Text Fields
        for entry in [self.entry_tag, self.entry_link, self.entry_sheet, self.entry_chart_id, self.edit_word_path]:
            entry.configure(
                fg_color=colors["surface"],
                border_color=colors["border"],
                text_color=colors["text"]
            )
            
        # Preview Box
        self.preview_box.configure(fg_color=colors["surface"], border_color=colors["border"])
        self.lbl_empty_title.configure(text_color=colors["textSecondary"])
        self.lbl_empty_desc.configure(text_color=colors["textMuted"])

        # Treeview Custom Styling
        style = ttk.Style()
        style.configure("Treeview", 
                        background=colors["surface"], 
                        foreground=colors["text"], 
                        fieldbackground=colors["surface"],
                        bordercolor=colors["border"])
        style.map("Treeview", 
                  background=[("selected", colors["primarySoft"])], 
                  foreground=[("selected", colors["primary"])])

    def init_ui(self):
        # Configure grid layout: row 0 is navigation, row 1 is main area
        self.grid_columnconfigure(0, weight=65)
        self.grid_columnconfigure(1, weight=35, minsize=360)
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
            header_bar, text="ВЕРСТКА ДИАГРАММ", font=("Segoe UI", 14, "bold"),
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
            columns=("Tag", "Link", "Sheet", "ChartId"),
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
        self.table_widget.heading("ChartId", text="ChartId (№ графика)")

        self.table_widget.column("Tag", width=140, anchor="w")
        self.table_widget.column("Link", width=250, anchor="w")
        self.table_widget.column("Sheet", width=100, anchor="w")
        self.table_widget.column("ChartId", width=100, anchor="center")

        self.table_widget.bind("<<TreeviewSelect>>", self.row_selected)

        # 2. Row Editor Frame (Row 2) - inputs to modify selected row
        editor_frame = customtkinter.CTkFrame(middle_widget, fg_color="#18181b", border_width=1, border_color="#27272a", corner_radius=6)
        editor_frame.grid(row=2, column=0, sticky="ew", pady=(0, 10), padx=2)
        
        customtkinter.CTkLabel(editor_frame, text="Tag:", font=("Segoe UI", 11)).grid(row=0, column=0, padx=8, pady=8, sticky="e")
        self.entry_tag = customtkinter.CTkEntry(editor_frame, width=120, font=("Segoe UI", 11))
        self.entry_tag.grid(row=0, column=1, padx=4, pady=8, sticky="w")

        customtkinter.CTkLabel(editor_frame, text="Link:", font=("Segoe UI", 11)).grid(row=0, column=2, padx=8, pady=8, sticky="e")
        self.entry_link = customtkinter.CTkEntry(editor_frame, width=220, font=("Segoe UI", 11))
        self.entry_link.grid(row=0, column=3, padx=4, pady=8, sticky="w")
        self.btn_browse_excel = customtkinter.CTkButton(editor_frame, text="...", width=28, height=28, command=self.browse_excel_file)
        self.btn_browse_excel.grid(row=0, column=4, padx=2, pady=8, sticky="w")

        customtkinter.CTkLabel(editor_frame, text="Лист:", font=("Segoe UI", 11)).grid(row=0, column=5, padx=8, pady=8, sticky="e")
        self.entry_sheet = customtkinter.CTkEntry(editor_frame, width=100, font=("Segoe UI", 11))
        self.entry_sheet.grid(row=0, column=6, padx=4, pady=8, sticky="w")

        customtkinter.CTkLabel(editor_frame, text="№ графика:", font=("Segoe UI", 11)).grid(row=0, column=7, padx=8, pady=8, sticky="e")
        self.entry_chart_id = customtkinter.CTkEntry(editor_frame, width=70, font=("Segoe UI", 11))
        self.entry_chart_id.grid(row=0, column=8, padx=4, pady=8, sticky="w")

        self.btn_apply = customtkinter.CTkButton(
            editor_frame, text="Применить", width=90, height=28, 
            font=("Segoe UI", 11, "bold"), fg_color=accent["fg"], hover_color=accent["hover"], command=self.apply_row_changes
        )
        self.btn_apply.grid(row=0, column=9, padx=12, pady=8, sticky="e")

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
        preview_panel = customtkinter.CTkFrame(self, fg_color="transparent")
        preview_panel.grid(row=1, column=1, sticky="nsew", padx=(6, 12), pady=12)
        preview_panel.grid_columnconfigure(0, weight=1)
        preview_panel.grid_rowconfigure(1, weight=1)

        lbl_preview = customtkinter.CTkLabel(preview_panel, text="Предпросмотр", font=("Segoe UI", 12, "bold"), text_color="#888888")
        lbl_preview.grid(row=0, column=0, sticky="w", pady=(0, 6))

        self.preview_box = customtkinter.CTkFrame(preview_panel, fg_color="#151515", border_width=1, border_color="#2d2d2d")
        self.preview_box.grid(row=1, column=0, sticky="nsew")
        self.preview_box.grid_columnconfigure(0, weight=1)
        self.preview_box.grid_rowconfigure(0, weight=1)

        # Image label inside preview box (hidden by default)
        self.preview_label = customtkinter.CTkLabel(self.preview_box, text="")
        
        # Empty state layout
        self.empty_preview_frame = customtkinter.CTkFrame(self.preview_box, fg_color="transparent")
        self.empty_preview_frame.pack(fill="both", expand=True, padx=16, pady=30)
        
        self.lbl_empty_title = customtkinter.CTkLabel(
            self.empty_preview_frame, text="Диаграмма пока не загружена", 
            font=("Segoe UI", 12, "bold")
        )
        self.lbl_empty_title.pack(fill="x", pady=(0, 6))
        
        self.lbl_empty_desc = customtkinter.CTkLabel(
            self.empty_preview_frame, text="Выберите ChartTag и нажмите «Предпросмотр», чтобы увидеть график из Excel.",
            font=("Segoe UI", 11), wraplength=180, justify="center"
        )
        self.lbl_empty_desc.pack(fill="x")
        
        # Preview button
        self.btn_load_prev = customtkinter.CTkButton(
            preview_panel, text="Предпросмотр", height=32, font=("Segoe UI", 11, "bold"),
            command=self.load_preview
        )
        self.btn_load_prev.grid(row=2, column=0, sticky="ew", pady=(8, 0))

    def go_back(self):
        # Save config changes before returning
        self.save_data(show_msg=False)
        if hasattr(self.controller, "show_dashboard"):
            self.controller.show_dashboard()

    def load_preview(self):
        selection = self.table_widget.selection()
        if not selection:
            messagebox.showwarning("Предупреждение", "Пожалуйста, выберите строку в таблице.", parent=self)
            return

        values = self.table_widget.item(selection[0])["values"]
        tag_name = str(values[0]).strip()
        excel_path = str(values[1]).strip()
        sheet_name = str(values[2]).strip()
        chart_id_str = str(values[3]).strip()

        # Update empty label to loading state
        self.preview_label.configure(image="", text="")
        self.lbl_empty_title.configure(text="Загрузка превью...")
        self.lbl_empty_desc.configure(text="Подключение к Excel...")
        self.empty_preview_frame.pack(fill="both", expand=True, padx=20, pady=40)
        self.preview_label.pack_forget()
        self.update()

        if sys.platform != "win32":
            self.lbl_empty_title.configure(text="Не поддерживается")
            self.lbl_empty_desc.configure(text="Предпросмотр доступен только на Windows")
            return

        excel = None
        wb = None
        wb_was_already_open = False
        created_excel = False

        try:
            import win32com.client
            import tempfile

            if not excel_path:
                self.lbl_empty_title.configure(text="Путь к Excel пуст")
                self.lbl_empty_desc.configure(text="Укажите путь к файлу Excel.")
                return

            resolved_path = os.path.normpath(resolve_dynamic_path(excel_path, self.config_path))
            if not os.path.exists(resolved_path):
                self.lbl_empty_title.configure(text="Файл не найден")
                self.lbl_empty_desc.configure(text=f"Файл Excel не существует:\n{excel_path}")
                return

            # Connect or launch Excel
            try:
                excel = win32com.client.GetActiveObject("Excel.Application")
            except Exception:
                excel = win32com.client.Dispatch("Excel.Application")
                created_excel = True

            if created_excel:
                excel.Visible = False
            excel.DisplayAlerts = False

            # Check if workbook is already open
            for open_wb in excel.Workbooks:
                if os.path.normpath(open_wb.FullName).lower() == resolved_path.lower():
                    wb = open_wb
                    wb_was_already_open = True
                    break

            if wb is None:
                wb = excel.Workbooks.Open(resolved_path, UpdateLinks=False, ReadOnly=True, IgnoreReadOnlyRecommended=True)

            try:
                ws = wb.Worksheets(sheet_name)
            except Exception:
                self.lbl_empty_title.configure(text="Лист не найден")
                self.lbl_empty_desc.configure(text=f"Лист '{sheet_name}' не найден в файле.")
                return

            # Activate sheet and temporarily show Excel for rendering capture
            ws.Activate()
            if created_excel:
                excel.Visible = True
            excel.ScreenUpdating = True

            temp_dir = tempfile.gettempdir()
            clean_tag_name = re.sub(r'[^a-zA-Z0-9_]', '_', tag_name)
            temp_path = os.path.join(temp_dir, f"docbuilder_prev_{clean_tag_name}.png")

            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

            # Export chart
            try:
                try:
                    idx = int(chart_id_str)
                    chart_obj = ws.ChartObjects(idx)
                except Exception:
                    chart_obj = ws.ChartObjects(chart_id_str)
                
                chart_obj.Select()
                chart_obj.Chart.Export(temp_path, "PNG")
            except Exception as ex:
                self.lbl_empty_title.configure(text="Не удалось построить")
                self.lbl_empty_desc.configure(text="Проверьте путь к Excel-файлу, название листа и параметры выбранного тега.")
                logger.error(f"Failed to export chart preview: {ex}")
                return

            if created_excel:
                excel.Visible = False
            excel.ScreenUpdating = False

            # Display image
            if os.path.exists(temp_path):
                self.preview_img = tkinter.PhotoImage(file=temp_path)
                w = self.preview_img.width()
                h = self.preview_img.height()
                
                # Subsample to fit 350x350 box
                factor = 1
                if w > 350 or h > 350:
                    factor = max(w // 350, h // 350) + 1
                    self.preview_img = self.preview_img.subsample(factor, factor)

                self.empty_preview_frame.pack_forget()
                self.preview_label.configure(image=self.preview_img, text="")
                self.preview_label.pack(fill="both", expand=True, padx=8, pady=8)
            else:
                self.lbl_empty_title.configure(text="Ошибка изображения")
                self.lbl_empty_desc.configure(text="Файл превью не был сгенерирован.")

        except Exception as e:
            self.lbl_empty_title.configure(text="Не удалось построить")
            self.lbl_empty_desc.configure(text="Проверьте путь к Excel-файлу, название листа и параметры выбранного тега.")
            logger.error(f"Error loading chart preview: {e}")
        finally:
            # Cleanup
            if wb and not wb_was_already_open:
                try:
                    wb.Close(SaveChanges=False)
                except Exception:
                    pass
            if excel and created_excel:
                try:
                    excel.Quit()
                except Exception:
                    pass

    def copy_text_to_clipboard(self, text):
        if sys.platform == "win32":
            try:
                import win32clipboard
                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(win32clipboard.CF_UNICODETEXT, text)
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
        if sys.platform != "win32":
            messagebox.showwarning(
                "Не поддерживается", 
                "Захват графиков из Excel поддерживается только на ОС Windows с установленным Microsoft Excel.", 
                parent=self
            )
            return

        try:
            import win32com.client
            try:
                excel = win32com.client.GetActiveObject("Excel.Application")
            except Exception:
                messagebox.showwarning(
                    "Excel не запущен", 
                    "Пожалуйста, запустите Microsoft Excel, откройте нужную книгу и выберите график для копирования.", 
                    parent=self
                )
                return

            active_chart = excel.ActiveChart
            if active_chart is None:
                messagebox.showwarning(
                    "График не выбран", 
                    "Вы не выбрали график в Excel.\nПожалуйста, кликните на график в Excel, чтобы выделить его, и попробуйте снова.\n"
                    "Для добавления таблицы ячеек перейдите в меню 'Верстка таблиц'.", 
                    parent=self
                )
                return

            # Grab chart metadata
            chart_shape = active_chart.Parent  # ChartObject shape
            ws = chart_shape.Parent            # Worksheet
            wb = ws.Parent                     # Workbook

            excel_path = wb.FullName
            sheet_name = ws.Name
            chart_name = chart_shape.Name
            
            # Find the 1-based sequential index of the chart in ChartObjects
            chart_id = 1
            for idx, co in enumerate(ws.ChartObjects()):
                if co.Name == chart_name:
                    chart_id = idx + 1
                    break

            # Resolve relative path if config_path is loaded
            if self.config_path:
                try:
                    rel = os.path.relpath(excel_path, os.path.dirname(self.config_path))
                    if not rel.startswith(".."):
                        excel_path = rel
                except ValueError:
                    pass

            # Generate unique tag ChartTag_N
            max_num = 0
            for child in self.table_widget.get_children():
                tag_val = self.table_widget.item(child)["values"][0]
                num_match = re.search(r'\d+', tag_val)
                if num_match:
                    max_num = max(max_num, int(num_match.group(0)))
            new_tag = f"<ChartTag_{max_num + 1}>"

            # Insert into Treeview
            new_row_id = self.table_widget.insert("", "end", values=(
                new_tag,
                excel_path,
                sheet_name,
                str(chart_id)
            ))

            # Select and refresh editor
            self.table_widget.selection_set(new_row_id)
            self.table_widget.see(new_row_id)
            self.row_selected()

            # Copy tag to clipboard
            self.copy_text_to_clipboard(new_tag)

            messagebox.showinfo(
                "Успешный захват",
                f"Успешно импортирован график № {chart_id} ('{chart_name}') на листе '{sheet_name}'.\n\n"
                f"Создан новый тег: {new_tag} (скопирован в буфер обмена!).\n"
                f"Вставьте тег (Ctrl+V) в нужное место в Word.",
                parent=self
            )

        except Exception as e:
            messagebox.showerror("Ошибка импорта", f"Произошел сбой при получении графика:\n{e}", parent=self)

    def load_config_data(self):
        self.refresh_theme_colors()
        self.edit_word_path.delete(0, "end")
        self.edit_word_path.insert(0, self.config.output_path)

        # Clear treeview
        for item in self.table_widget.get_children():
            self.table_widget.delete(item)

        for item in self.config.charts:
            self.table_widget.insert("", "end", values=(
                item.tag,
                item.excel_path,
                item.sheet,
                str(item.chart_id)
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

        self.entry_chart_id.delete(0, "end")
        self.entry_chart_id.insert(0, values[3])

    def apply_row_changes(self):
        selection = self.table_widget.selection()
        if not selection:
            messagebox.showwarning("Предупреждение", "Пожалуйста, выберите строку для редактирования.", parent=self)
            return

        tag = self.entry_tag.get().strip()
        link = self.entry_link.get().strip()
        sheet = self.entry_sheet.get().strip()
        chart_id_str = self.entry_chart_id.get().strip()

        if not tag:
            messagebox.showwarning("Ошибка", "Тег не может быть пустым.", parent=self)
            return

        try:
            int(chart_id_str)
        except ValueError:
            messagebox.showwarning("Ошибка", "Номер графика должен быть целым числом.", parent=self)
            return

        self.table_widget.item(selection[0], values=(tag, link, sheet, chart_id_str))

    def add_row(self):
        new_row_id = self.table_widget.insert("", "end", values=(
            "<ChartTag_New>", "", "Charts", "1"
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
            self.entry_chart_id.delete(0, "end")
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
        if not selection:
            messagebox.showwarning("Предупреждение", "Выберите строку с диаграммой для просмотра.", parent=self)
            return

        values = self.table_widget.item(selection[0])["values"]
        excel_path = str(values[1]).strip()
        sheet_name = str(values[2]).strip()
        chart_id_str = str(values[3]).strip()

        if not excel_path:
            messagebox.showwarning("Предупреждение", "В выбранной строке не указан путь к Excel-файлу.", parent=self)
            return

        resolved_path = resolve_dynamic_path(excel_path, self.config_path)
        if not os.path.exists(resolved_path):
            err_msg = "Excel-файл не найден или недоступен"
            logger.error(f"{err_msg}: {excel_path}")
            messagebox.showerror("Ошибка", err_msg, parent=self)
            return

        logger.info(f"Opening Excel file: {resolved_path}")
        if sys.platform != "win32":
            try:
                if sys.platform == "darwin":
                    import subprocess
                    subprocess.run(["open", resolved_path])
                else:
                    import subprocess
                    subprocess.run(["xdg-open", resolved_path])
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось открыть файл:\n{e}", parent=self)
            return

        try:
            import win32com.client
            # Try to connect to Excel, or launch it if not open
            try:
                excel = win32com.client.GetActiveObject("Excel.Application")
            except Exception:
                excel = win32com.client.Dispatch("Excel.Application")
            
            excel.Visible = True
            
            # Check if workbook is already open
            wb = None
            for open_wb in excel.Workbooks:
                if os.path.normpath(open_wb.FullName).lower() == os.path.normpath(resolved_path).lower():
                    wb = open_wb
                    break
            
            if wb is None:
                wb = excel.Workbooks.Open(resolved_path)
            
            # Activate worksheet
            try:
                ws = wb.Worksheets(sheet_name)
                ws.Activate()
                
                # Activate/select chart if possible
                if chart_id_str:
                    try:
                        try:
                            idx = int(chart_id_str)
                            chart_obj = ws.ChartObjects(idx)
                        except Exception:
                            chart_obj = ws.ChartObjects(chart_id_str)
                        
                        chart_obj.Select()
                    except Exception as re:
                        logger.warning(f"Не удалось выбрать график {chart_id_str} на листе '{sheet_name}': {re}")
            except Exception:
                # Sheet not found
                msg = f"Лист не найден: {sheet_name}"
                logger.warning(msg)
                messagebox.showwarning("Предупреждение", msg, parent=self)
                
        except Exception as e:
            logger.error(f"Не удалось открыть Excel: {e}")
            messagebox.showerror("Ошибка", f"Не удалось открыть файл:\n{e}", parent=self)

    def save_data(self, show_msg: bool = True) -> bool:
        norm = os.path.normpath(self.edit_word_path.get().strip())
        self.config.output_path = norm
        self.config.template_path = norm

        charts = []
        for child in self.table_widget.get_children():
            values = self.table_widget.item(child)["values"]
            tag = str(values[0]).strip()
            link = str(values[1]).strip()
            sheet = str(values[2]).strip()
            chart_id_str = str(values[3]).strip()
            
            try:
                chart_id = int(chart_id_str)
            except (ValueError, TypeError):
                chart_id = 1

            if tag:
                charts.append(ChartItem(
                    tag=tag,
                    excel_path=link,
                    sheet=sheet,
                    chart_id=chart_id
                ))

        self.config.charts = charts
        
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
        
        logger.info("Запуск верстки диаграмм...")
        self.btn_launch.configure(state="disabled", text="ВЕРСТКА...")
        self.update()

        try:
            errors = report_builder.build_report(
                config=self.config,
                config_path=self.config_path,
                run_tables=False,
                run_charts=True,
                clean_tags=False,
                status_callback=lambda msg: (logger.info(msg), self.update())
            )
            
            if errors:
                err_msg = "\n".join(errors[:10])
                if len(errors) > 10:
                    err_msg += f"\n...и еще {len(errors) - 10} ошибок."
                messagebox.showwarning("Верстка диаграмм завершена с ошибками", f"Некоторые диаграммы не верстались:\n\n{err_msg}", parent=self)
            else:
                messagebox.showinfo("Успех", f"Верстка диаграмм завершена успешно!\nРезультат сохранен в:\n{self.config.output_path}", parent=self)
        except Exception as e:
            messagebox.showerror("Ошибка верстки", f"Процесс завершился сбоем:\n{e}", parent=self)
        finally:
            self.btn_launch.configure(state="normal", text="ЗАПУСК")
            if hasattr(self.parent_window, "update_ui_from_config"):
                self.parent_window.update_ui_from_config()
