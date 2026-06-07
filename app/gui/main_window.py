import os
import sys
import logging
import tkinter
import re
from tkinter import messagebox, filedialog
import customtkinter

from app.models.config import ReportConfig, TableItem, ChartItem
from app.services import config_loader, report_builder
from app.gui.tables_window import TablesWindow
from app.gui.charts_window import ChartsWindow
from app.gui.tags_window import TagsWindow
from app.gui.widgets.log_viewer import LogViewer
from app.utils.paths import resolve_dynamic_path

logger = logging.getLogger("DocBuilder.MainWindow")

class ActionCard(customtkinter.CTkFrame):
    def __init__(self, title, description, command=None, color_theme="blue", parent=None):
        super().__init__(parent, fg_color="transparent", border_width=1, border_color="#27272a", corner_radius=8)
        self.command = command
        self.color_theme = color_theme
        self.theme = None
        
        # Configure layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self.lbl_title = customtkinter.CTkLabel(
            self, text=title, font=("Segoe UI", 13, "bold"), anchor="w"
        )
        self.lbl_title.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 4))

        self.lbl_desc = customtkinter.CTkLabel(
            self, text=description, font=("Segoe UI", 11), text_color="#a1a1aa",
            wraplength=200, justify="left", anchor="nw"
        )
        self.lbl_desc.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 14))

        # Bind hover and click events
        for widget in [self, self.lbl_title, self.lbl_desc]:
            widget.bind("<Button-1>", self.on_click)
            widget.bind("<Enter>", self.on_enter)
            widget.bind("<Leave>", self.on_leave)

    def update_style(self, theme):
        self.theme = theme
        colors = theme["colors"]
        is_dark = (theme["mode"] == "dark")
        
        bg = colors["surface"]
        border = colors["border"]
        desc_color = colors["textSecondary"]
        
        if self.color_theme == "blue":
            self.title_color = colors["primary"]
        elif self.color_theme == "purple":
            self.title_color = "#c084fc" if is_dark else "#7c3aed"
        elif self.color_theme == "amber":
            self.title_color = "#fbbf24" if is_dark else "#b45309"
        elif self.color_theme == "red":
            self.title_color = colors["danger"]
        else:
            self.title_color = colors["primary"]
            
        self.configure(fg_color=bg, border_color=border)
        self.lbl_title.configure(text_color=self.title_color)
        self.lbl_desc.configure(text_color=desc_color)

    def on_enter(self, event=None):
        if self.theme:
            colors = self.theme["colors"]
            self.configure(fg_color=colors["surface2"], border_color=colors["primary"] if self.color_theme == "blue" else colors["border"])

    def on_leave(self, event=None):
        if self.theme:
            colors = self.theme["colors"]
            self.configure(fg_color=colors["surface"], border_color=colors["border"])

    def on_click(self, event=None):
        if self.command:
            self.command()


class MainWindow(customtkinter.CTk):
    def __init__(self):
        super().__init__()
        self.title("DocBuilder_v2.0 | Панель управления")
        self.geometry("1200x780")
        
        self.config = ReportConfig()
        self.config_path = ""
        self.is_dark_theme = True
        
        # Navigation container for single-window design
        self.container = customtkinter.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True)
        
        # Active child frames
        self.tables_frame = None
        self.charts_frame = None
        self.tags_frame = None
        self.config_builder_frame = None
        self.config_builder_window = None
        self.current_frame = None

        self.init_ui()
        self.apply_theme()
        
        # Show dashboard initially
        self.show_dashboard()
        logger.info("Программа запущена.")

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

    def apply_accent_theme_colors(self):
        accent = self.get_accent_theme()
        self.btn_quick_grab.configure(fg_color=accent["fg"], hover_color=accent["hover"])
        self.tags_list.configure(selectforeground=accent["fg"])
        if hasattr(self, "btn_open_builder"):
            self.btn_open_builder.configure(
                fg_color="#27272a" if self.is_dark_theme else "#e4e4e7", 
                hover_color="#3f3f46" if self.is_dark_theme else "#cbd5e1",
                text_color="#ffffff" if self.is_dark_theme else "#18181b"
            )

    def init_ui(self):
        # 1. Main Dashboard Frame
        self.dashboard_frame = customtkinter.CTkFrame(self.container, fg_color="transparent")
        
        # Grid layout (Left panel column 0, Right panel column 1)
        self.dashboard_frame.grid_columnconfigure(0, weight=25, minsize=260)
        self.dashboard_frame.grid_columnconfigure(1, weight=75, minsize=940)
        self.dashboard_frame.grid_rowconfigure(0, weight=1)

        # Left Panel (Tag List & Toolbar)
        self.left_panel = customtkinter.CTkFrame(self.dashboard_frame, corner_radius=0, fg_color="transparent")
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)
        self.left_panel.grid_columnconfigure(0, weight=1)
        self.left_panel.grid_rowconfigure(3, weight=1)

        left_toolbar = customtkinter.CTkFrame(self.left_panel, fg_color="transparent")
        left_toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        self.btn_load_config = customtkinter.CTkButton(
            left_toolbar, text="Открыть конфигурацию", height=32,
            font=("Segoe UI", 11, "bold"), command=self.open_config
        )
        self.btn_load_config.pack(side="left", fill="x", expand=True, padx=(0, 4))
        
        self.btn_theme = customtkinter.CTkButton(
            left_toolbar, text="☀️ СВЕТЛАЯ ТЕМА", width=110, height=32,
            font=("Segoe UI", 10, "bold"), command=self.toggle_theme
        )
        self.btn_theme.pack(side="right")

        # Config Setup & Tag Management trigger button
        self.btn_open_builder = customtkinter.CTkButton(
            self.left_panel, text="⚙️ Настройка проекта и тегов (JSON)", height=32,
            font=("Segoe UI", 11, "bold"), command=self.show_config_builder
        )
        self.btn_open_builder.grid(row=1, column=0, sticky="ew", pady=(0, 8))

        # Checkbox to toggle JSON colors usage
        self.val_use_json_colors = tkinter.BooleanVar(value=True)
        self.chk_use_json_colors = customtkinter.CTkCheckBox(
            self.left_panel, text="Использовать цвета JSON", font=("Segoe UI", 11),
            variable=self.val_use_json_colors, command=self.apply_theme
        )
        self.chk_use_json_colors.grid(row=2, column=0, sticky="w", pady=(0, 8), padx=4)

        # Search input for tag filtering
        self.search_input = customtkinter.CTkEntry(self.left_panel, placeholder_text="Поиск тегов...")
        self.search_input.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        self.search_input.bind("<KeyRelease>", self.filter_tags)

        # Tag List Container (Listbox + Scrollbar)
        self.left_panel.grid_rowconfigure(3, weight=0)
        self.left_panel.grid_rowconfigure(4, weight=1)
        list_container = customtkinter.CTkFrame(self.left_panel, fg_color="transparent")
        list_container.grid(row=4, column=0, sticky="nsew")
        list_container.grid_columnconfigure(0, weight=1)
        list_container.grid_rowconfigure(0, weight=1)

        self.tags_list = tkinter.Listbox(
            list_container,
            bg="#0c0c0e",
            fg="#e4e4e7",
            selectbackground="#27272a",
            selectforeground="#3b82f6",
            bd=1,
            highlightthickness=1,
            highlightbackground="#1f1f24",
            highlightcolor="#3b82f6",
            font=("Segoe UI", 11),
            relief="flat"
        )
        self.tags_list.grid(row=0, column=0, sticky="nsew")

        scrollbar = customtkinter.CTkScrollbar(list_container, orientation="vertical", command=self.tags_list.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tags_list.config(yscrollcommand=scrollbar.set)

        # Right Panel (Logs, Info, Buttons Grid)
        self.right_panel = customtkinter.CTkFrame(self.dashboard_frame, corner_radius=0, fg_color="transparent")
        self.right_panel.grid(row=0, column=1, sticky="nsew", padx=(10, 15), pady=15)
        self.right_panel.grid_columnconfigure(0, weight=1)
        self.right_panel.grid_rowconfigure(0, weight=3) # Log viewer gets weight
        self.right_panel.grid_rowconfigure(1, weight=0) # Word file row
        self.right_panel.grid_rowconfigure(2, weight=2) # Bottom panel

        # Logs Viewer (Top right)
        self.log_viewer = LogViewer(self.right_panel)
        self.log_viewer.grid(row=0, column=0, sticky="nsew", pady=(0, 12))

        # Word File Input Row
        word_card = customtkinter.CTkFrame(self.right_panel, fg_color="transparent")
        word_card.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        word_card.grid_columnconfigure(1, weight=1)

        lbl_word = customtkinter.CTkLabel(word_card, text="Файл верстки (Word):", font=("Segoe UI", 11, "bold"))
        lbl_word.grid(row=0, column=0, padx=(0, 8), pady=4)

        self.edit_word_path = customtkinter.CTkEntry(word_card, placeholder_text="Выберите скопированный документ Word для сборки отчета...")
        self.edit_word_path.grid(row=0, column=1, sticky="ew", padx=(0, 6), pady=4)
        self.edit_word_path.bind("<KeyRelease>", lambda e: self.word_path_changed(self.edit_word_path.get()))

        self.btn_word_browse = customtkinter.CTkButton(word_card, text="...", width=32, height=28, command=self.browse_word_file)
        self.btn_word_browse.grid(row=0, column=2, padx=(0, 6), pady=4)

        self.btn_word_open = customtkinter.CTkButton(
            word_card, text="ОТКРЫТЬ", width=90, height=28,
            fg_color="#059669", hover_color="#047857", text_color="#ffffff",
            font=("Segoe UI", 11, "bold"), command=self.open_word_file
        )
        self.btn_word_open.grid(row=0, column=3, pady=4)

        # Bottom Panel (Info Panel + Action Grid)
        bottom_panel = customtkinter.CTkFrame(self.right_panel, fg_color="transparent")
        bottom_panel.grid(row=2, column=0, sticky="nsew")
        bottom_panel.grid_columnconfigure(0, weight=0, minsize=340)
        bottom_panel.grid_columnconfigure(1, weight=2)
        bottom_panel.grid_rowconfigure(0, weight=1)

        # Info Card
        self.info_panel = customtkinter.CTkFrame(
            bottom_panel, fg_color="#121218", border_width=1, border_color="#1a1a22", corner_radius=6
        )
        self.info_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        self.info_panel.grid_columnconfigure(0, weight=1)

        info_title = customtkinter.CTkLabel(
            self.info_panel, text="Инфо данные", font=("Segoe UI", 10, "bold"), text_color="#888892"
        )
        info_title.grid(row=0, column=0, sticky="w", padx=15, pady=(12, 6))

        self.config_header_frame = customtkinter.CTkFrame(self.info_panel, fg_color="transparent")
        self.config_header_frame.grid(row=1, column=0, sticky="w", padx=15, pady=3)

        self.lbl_info_config = customtkinter.CTkLabel(
            self.config_header_frame, text="Файл настроек: (Конфигурация не загружена)",
            font=("Segoe UI", 11, "bold"), text_color="#60a5fa"
        )
        self.lbl_info_config.pack(side="left")

        self.lbl_accent_badge = customtkinter.CTkLabel(
            self.config_header_frame, text="",
            font=("Segoe UI", 9, "bold"),
            fg_color="#3B82F6", text_color="#ffffff",
            corner_radius=4, height=16, padx=6
        )
        self.lbl_accent_badge.pack(side="left", padx=(8, 0))
        self.lbl_accent_badge.pack_forget()

        self.lbl_info_output = customtkinter.CTkLabel(
            self.info_panel, text="Файл верстки: -", font=("Segoe UI", 11), text_color="#d4d4d8",
            wraplength=310, justify="left", anchor="w"
        )
        self.lbl_info_output.grid(row=2, column=0, sticky="w", padx=15, pady=3)

        self.lbl_info_stats = customtkinter.CTkLabel(
            self.info_panel, text="Загружено тегов: 0 | Таблиц: 0 | Диаграмм: 0",
            font=("Segoe UI", 11), text_color="#d4d4d8"
        )
        self.lbl_info_stats.grid(row=3, column=0, sticky="w", padx=15, pady=3)

        # Quick import from Excel Button inside Info Card (Row 4)
        accent = self.get_accent_theme()
        self.btn_quick_grab = customtkinter.CTkButton(
            self.info_panel, text="⚡ БЫСТРЫЙ ИМПОРТ ИЗ EXCEL", height=32,
            font=("Segoe UI", 11, "bold"), fg_color=accent["fg"], hover_color=accent["hover"],
            command=self.quick_grab_from_excel
        )
        self.btn_quick_grab.grid(row=4, column=0, sticky="ew", padx=15, pady=(12, 12))

        # Action Cards Grid
        buttons_grid_widget = customtkinter.CTkFrame(bottom_panel, fg_color="transparent")
        buttons_grid_widget.grid(row=0, column=1, sticky="nsew")
        buttons_grid_widget.grid_columnconfigure(0, weight=1)
        buttons_grid_widget.grid_columnconfigure(1, weight=1)
        buttons_grid_row_count = 2
        buttons_grid_widget.grid_rowconfigure(0, weight=1)
        buttons_grid_widget.grid_rowconfigure(1, weight=1)

        self.btn_vert_articles = ActionCard(
            "Текстовые статьи", 
            "Просмотр и редактирование текстового наполнения отчета (топиков)", 
            command=self.show_tags, color_theme="amber", parent=buttons_grid_widget
        )
        self.btn_vert_articles.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)

        self.btn_vert_charts = ActionCard(
            "Диаграммы и графики", 
            "Импорт диаграмм из Excel в Word с точными размерами в пикселях", 
            command=self.show_charts, color_theme="purple", parent=buttons_grid_widget
        )
        self.btn_vert_charts.grid(row=0, column=1, sticky="nsew", padx=6, pady=6)

        self.btn_vert_tables = ActionCard(
            "Таблицы Excel", 
            "Сборка и верстка табличных диапазонов из Excel-листов", 
            command=self.show_tables, color_theme="blue", parent=buttons_grid_widget
        )
        self.btn_vert_tables.grid(row=1, column=0, sticky="nsew", padx=6, pady=6)

        self.btn_tech_clean = ActionCard(
            "Техническая очистка", 
            "Очистка Word-документа от всех неиспользованных тегов верстки", 
            command=self.run_technical_cleanup, color_theme="red", parent=buttons_grid_widget
        )
        self.btn_tech_clean.grid(row=1, column=1, sticky="nsew", padx=6, pady=6)

    def show_dashboard(self):
        # Hide any active frame
        if self.current_frame:
            self.current_frame.pack_forget()
        
        self.dashboard_frame.pack(fill="both", expand=True)
        self.current_frame = self.dashboard_frame
        self.title("DocBuilder | Панель управления")
        self.update_ui_from_config()

    def show_tables(self):
        if not self.config_path:
            messagebox.showwarning("Предупреждение", "Пожалуйста, сначала откройте файл конфигурации JSON.", parent=self)
            return
        
        if self.tables_frame is None:
            self.tables_frame = TablesWindow(self.container, self, self.config, self.config_path)
            self.tables_frame.config_updated_connect(self.update_ui_from_config)
        else:
            self.tables_frame.config = self.config
            self.tables_frame.config_path = self.config_path
            self.tables_frame.load_config_data()

        self.dashboard_frame.pack_forget()
        self.tables_frame.pack(fill="both", expand=True)
        self.current_frame = self.tables_frame
        self.title("DocBuilder | Верстка таблиц")

    def show_charts(self):
        if not self.config_path:
            messagebox.showwarning("Предупреждение", "Пожалуйста, сначала откройте файл конфигурации JSON.", parent=self)
            return
        
        if self.charts_frame is None:
            self.charts_frame = ChartsWindow(self.container, self, self.config, self.config_path)
            self.charts_frame.config_updated_connect(self.update_ui_from_config)
        else:
            self.charts_frame.config = self.config
            self.charts_frame.config_path = self.config_path
            self.charts_frame.load_config_data()

        self.dashboard_frame.pack_forget()
        self.charts_frame.pack(fill="both", expand=True)
        self.current_frame = self.charts_frame
        self.title("DocBuilder | Верстка диаграмм")

    def show_tags(self):
        if not self.config_path:
            messagebox.showwarning("Предупреждение", "Пожалуйста, сначала откройте файл конфигурации JSON.", parent=self)
            return
        
        if self.tags_frame is None:
            self.tags_frame = TagsWindow(self.container, self, self.config, self.config_path)
            self.tags_frame.config_updated_connect(self.update_ui_from_config)
        else:
            self.tags_frame.config = self.config
            self.tags_frame.config_path = self.config_path
            self.tags_frame.load_config_data()

        self.dashboard_frame.pack_forget()
        self.tags_frame.pack(fill="both", expand=True)
        self.current_frame = self.tags_frame
        self.title("DocBuilder | Текстовые статьи")

    def show_config_builder(self):
        # Builder can be opened even without config (starts a new blank JSON config or uses active)
        from app.gui.config_builder import ConfigBuilderWindow
        if self.config_builder_window is None or not self.config_builder_window.winfo_exists():
            self.config_builder_window = ConfigBuilderWindow(self, self)
        else:
            self.config_builder_window.config = self.config
            self.config_builder_window.config_path = self.config_path
            self.config_builder_window.load_config_data()
            self.config_builder_window.focus()

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

    def quick_grab_from_excel(self):
        if not self.config_path:
            messagebox.showwarning("Предупреждение", "Пожалуйста, сначала откройте файл конфигурации JSON.", parent=self)
            return

        if sys.platform != "win32":
            messagebox.showwarning(
                "Не поддерживается", 
                "Захват данных из Excel поддерживается только на ОС Windows с установленным Microsoft Excel.", 
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
                    "Пожалуйста, запустите Microsoft Excel, откройте нужную книгу и выберите диапазон ячеек или график.", 
                    parent=self
                )
                return

            active_chart = excel.ActiveChart
            # Case 1: Chart Grab
            if active_chart is not None:
                chart_shape = active_chart.Parent
                ws = chart_shape.Parent
                wb = ws.Parent

                excel_path = wb.FullName
                sheet_name = ws.Name
                chart_name = chart_shape.Name

                # Find the 1-based sequential index of the chart in ChartObjects
                chart_id = 1
                for idx, co in enumerate(ws.ChartObjects()):
                    if co.Name == chart_name:
                        chart_id = idx + 1
                        break

                if self.config_path:
                    try:
                        rel = os.path.relpath(excel_path, os.path.dirname(self.config_path))
                        if not rel.startswith(".."):
                            excel_path = rel
                    except ValueError:
                        pass

                # Find highest tag number
                max_num = 0
                for c in self.config.charts:
                    num_match = re.search(r'\d+', c.tag)
                    if num_match:
                        max_num = max(max_num, int(num_match.group(0)))
                new_tag = f"<ChartTag_{max_num + 1}>"

                # Append to config
                self.config.charts.append(ChartItem(
                    tag=new_tag,
                    excel_path=excel_path,
                    sheet=sheet_name,
                    chart_id=chart_id
                ))
                self.config.tags.append(new_tag)
                
                # Save config
                config_loader.save_config_json(self.config, self.config_path)
                self.update_ui_from_config()

                # Clipboard auto-copy
                self.copy_text_to_clipboard(new_tag)

                logger.info(f"Быстрый захват: добавлен график {new_tag}. Тег скопирован в буфер.")
                messagebox.showinfo(
                    "Успешный импорт графика",
                    f"Добавлен график № {chart_id} ('{chart_name}') на листе '{sheet_name}'.\n\n"
                    f"Создан новый тег: {new_tag} (скопирован в буфер обмена!).\n"
                    f"Вставьте тег (Ctrl+V) в нужное место в Word.",
                    parent=self
                )
                return

            # Case 2: Table/Range Grab
            wb = excel.ActiveWorkbook
            ws = excel.ActiveSheet
            sel = excel.Selection

            if wb is None or ws is None or sel is None:
                messagebox.showwarning("Ошибка выбора", "Не удалось обнаружить активное выделение в Excel.", parent=self)
                return

            if not hasattr(sel, "Address"):
                messagebox.showwarning("Ошибка выбора", "Пожалуйста, выделите диапазон ячеек или график в Excel.", parent=self)
                return

            excel_path = wb.FullName
            sheet_name = ws.Name
            address = sel.Address.replace('$', '')

            if ":" in address:
                range_a, range_b = address.split(":")
            else:
                range_a = address
                range_b = ""

            if self.config_path:
                try:
                    rel = os.path.relpath(excel_path, os.path.dirname(self.config_path))
                    if not rel.startswith(".."):
                        excel_path = rel
                except ValueError:
                    pass

            # Find highest tag number
            max_num = 0
            for t in self.config.tables:
                num_match = re.search(r'\d+', t.tag)
                if num_match:
                    max_num = max(max_num, int(num_match.group(0)))
            new_tag = f"<TableTag_{max_num + 1}>"

            # Append to config
            self.config.tables.append(TableItem(
                tag=new_tag,
                excel_path=excel_path,
                sheet=sheet_name,
                range_a=range_a,
                range_b=range_b,
                use=True,
                header=False
            ))
            self.config.tags.append(new_tag)

            # Save config
            config_loader.save_config_json(self.config, self.config_path)
            self.update_ui_from_config()

            # Clipboard copy
            self.copy_text_to_clipboard(new_tag)

            logger.info(f"Быстрый захват: добавлена таблица {new_tag}. Тег скопирован в буфер.")
            messagebox.showinfo(
                "Успешный импорт таблицы",
                f"Добавлен диапазон ячеек {range_a}:{range_b} на листе '{sheet_name}'.\n\n"
                f"Создан новый тег: {new_tag} (скопирован в буфер обмена!).\n"
                f"Вставьте тег (Ctrl+V) в нужное место в Word.",
                parent=self
            )

        except Exception as e:
            messagebox.showerror("Ошибка импорта", f"Не удалось считать выделение из Excel:\n{e}", parent=self)

    def get_theme(self) -> dict:
        mode = "dark" if self.is_dark_theme else "light"
        accent = "#3B82F6"
        
        # Check if the user opted out of JSON custom colors
        use_json_colors = True
        if hasattr(self, "val_use_json_colors"):
            use_json_colors = self.val_use_json_colors.get()
            
        if use_json_colors and self.config and getattr(self.config, "uiTheme", None) is not None:
            ui = self.config.uiTheme
            if ui.mode:
                mode = ui.mode
            if ui.accent:
                accent = ui.accent
        else:
            # Fallback to standard theme accent mapping
            theme_name = getattr(self.config, "accent_color", "blue") or "blue"
            THEME_ACCENTS = {
                "blue": "#3b82f6",
                "emerald": "#10b981",
                "rose": "#f43f5e",
                "amber": "#f59e0b",
                "purple": "#8b5cf6"
            }
            accent = THEME_ACCENTS.get(theme_name.lower(), "#3B82F6")
            
        # If we opt out of JSON config colors completely, force standard blue accent #3B82F6
        if not use_json_colors:
            accent = "#3B82F6"
            
        from app.utils.themes import buildTheme
        return buildTheme(mode, accent)

    def toggle_theme(self):
        self.is_dark_theme = not self.is_dark_theme
        if self.is_dark_theme:
            self.btn_theme.configure(text="☀️ СВЕТЛАЯ ТЕМА")
        else:
            self.btn_theme.configure(text="🌙 ТЕМНАЯ ТЕМА")
            
        if self.config:
            if getattr(self.config, "uiTheme", None) is None:
                from app.models.config import UITheme
                self.config.uiTheme = UITheme()
            self.config.uiTheme.mode = "dark" if self.is_dark_theme else "light"
            if self.config_path:
                try:
                    config_loader.save_config_json(self.config, self.config_path)
                except Exception as e:
                    logger.error(f"Failed to auto-save theme change: {e}")
                    
        self.apply_theme()

    def apply_theme(self):
        """Applies dark or light theme styles globally using theme tokens."""
        theme = self.get_theme()
        colors = theme["colors"]
        is_dark = (theme["mode"] == "dark")
        
        customtkinter.set_appearance_mode("Dark" if is_dark else "Light")
        
        self.configure(fg_color=colors["bg"])
        self.container.configure(fg_color=colors["bg"])
        self.dashboard_frame.configure(fg_color=colors["bg"])
        
        # Style input fields
        self.search_input.configure(
            fg_color=colors["surface"],
            border_color=colors["border"],
            text_color=colors["text"]
        )
        self.edit_word_path.configure(
            fg_color=colors["surface"],
            border_color=colors["border"],
            text_color=colors["text"]
        )
        
        # Style standard buttons
        for btn in [self.btn_load_config, self.btn_theme, self.btn_open_builder, self.btn_word_browse]:
            btn.configure(
                fg_color=colors["surface2"],
                hover_color=colors["border"],
                text_color=colors["text"]
            )
            
        # Style primary action buttons
        self.btn_quick_grab.configure(
            fg_color=colors["primary"],
            hover_color=colors["primaryHover"],
            text_color="#ffffff"
        )
        self.btn_word_open.configure(
            fg_color=colors["success"],
            hover_color=colors["primaryHover"],
            text_color="#ffffff"
        )
        
        # Info panel cards and badges
        self.info_panel.configure(fg_color=colors["surface"], border_color=colors["border"])
        self.lbl_info_config.configure(text_color=colors["primary"])
        self.lbl_info_output.configure(text_color=colors["textSecondary"])
        self.lbl_info_stats.configure(text_color=colors["textSecondary"])
        
        self.lbl_accent_badge.configure(
            fg_color=colors["primarySoft"],
            text_color=colors["primary"]
        )
        
        # Style tags list & theme checkbox
        self.tags_list.configure(
            bg=colors["surface"],
            fg=colors["text"],
            selectbackground=colors["primarySoft"],
            selectforeground=colors["primary"],
            highlightbackground=colors["border"],
            highlightcolor=colors["primary"]
        )
        if hasattr(self, "chk_use_json_colors"):
            self.chk_use_json_colors.configure(text_color=colors["text"])
        
        # Action cards
        for card in [self.btn_vert_articles, self.btn_vert_charts, self.btn_vert_tables, self.btn_tech_clean]:
            card.update_style(theme)
            
        # Child windows
        if self.config_builder_frame is not None:
            self.config_builder_frame.refresh_theme_colors()
        if self.tables_frame is not None:
            self.tables_frame.refresh_theme_colors()
        if self.charts_frame is not None:
            self.charts_frame.refresh_theme_colors()
        if self.tags_frame is not None:
            self.tags_frame.refresh_theme_colors()
            
        # Log viewer
        if hasattr(self, "log_viewer"):
            self.log_viewer.refresh_theme_colors(theme)

    # --- Actions ---
    def open_config(self):
        file_path = filedialog.askopenfilename(
            title="Открыть конфигурацию JSON",
            filetypes=[("Файлы JSON", "*.json")]
        )
        if file_path:
            try:
                self.config = config_loader.load_config_json(file_path)
                self.config_path = os.path.normpath(file_path)
                self.update_ui_from_config()
                logger.info(f"Загружены настройки из файла: {self.config_path}")
            except Exception as e:
                logger.error(f"Не удалось открыть конфигурацию JSON: {e}")
                messagebox.showerror("Ошибка загрузки", f"Не удалось загрузить файл конфигурации:\n{e}", parent=self)

    def word_path_changed(self, text):
        norm = os.path.normpath(text.strip())
        self.config.output_path = norm
        self.config.template_path = norm
        self.lbl_info_output.configure(text=f"Файл верстки: {norm or '-'}")

    def browse_word_file(self):
        initial_dir = getattr(self.config, "default_word_dir", "")
        if not initial_dir or not os.path.exists(resolve_dynamic_path(initial_dir, self.config_path)):
            initial_dir = os.path.dirname(self.config_path) if self.config_path else os.getcwd()
        else:
            initial_dir = resolve_dynamic_path(initial_dir, self.config_path)

        file_path = filedialog.askopenfilename(
            title="Выберите файл верстки Word",
            initialdir=initial_dir,
            filetypes=[("Документы Word", "*.docx *.docm")]
        )
        if file_path:
            norm_path = os.path.normpath(file_path)
            self.edit_word_path.delete(0, "end")
            self.edit_word_path.insert(0, norm_path)
            self.word_path_changed(norm_path)
            logger.info(f"Выбран файл верстки: {norm_path}")

    def open_word_file(self):
        path = self.edit_word_path.get().strip()
        resolved = resolve_dynamic_path(path, self.config_path)
        if resolved and os.path.exists(resolved):
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

    def update_ui_from_config(self):
        """Refreshes tag list and info details."""
        self.tags_list.delete(0, "end")
        for tag in self.config.tags:
            self.tags_list.insert("end", tag)
            
        config_name = os.path.basename(self.config_path) if self.config_path else "(Конфигурация не сохранена)"
        self.lbl_info_config.configure(text=f"Файл настроек: {config_name}")
        
        # Display badge with accentName if present
        accent_name = None
        if self.config and getattr(self.config, "uiTheme", None) is not None:
            ui = self.config.uiTheme
            accent_name = getattr(ui, "accentName", None)
            
        if accent_name:
            self.lbl_accent_badge.configure(text=accent_name)
            self.lbl_accent_badge.pack(side="left", padx=(8, 0))
        else:
            self.lbl_accent_badge.pack_forget()
            
        # Synchronize self.is_dark_theme with loaded configuration theme mode
        if self.config and getattr(self.config, "uiTheme", None) is not None:
            ui = self.config.uiTheme
            if ui.mode:
                self.is_dark_theme = (ui.mode == "dark")
                if self.is_dark_theme:
                    self.btn_theme.configure(text="☀️ СВЕТЛАЯ ТЕМА")
                else:
                    self.btn_theme.configure(text="🌙 ТЕМНАЯ ТЕМА")
        
        self.edit_word_path.delete(0, "end")
        self.edit_word_path.insert(0, self.config.output_path)
        
        self.lbl_info_output.configure(text=f"Файл верстки: {self.config.output_path or '-'}")
        self.lbl_info_stats.configure(
            text=f"Загружено тегов: {len(self.config.tags)} | Таблиц: {len(self.config.tables)} | Диаграмм: {len(self.config.charts)}"
        )
        
        # Apply theme colors
        self.apply_theme()

    def filter_tags(self, event=None):
        query = self.search_input.get().lower().strip()
        self.tags_list.delete(0, "end")
        for tag in self.config.tags:
            if query in tag.lower():
                self.tags_list.insert("end", tag)

    def run_technical_cleanup(self):
        if not self.config_path:
            messagebox.showwarning("Предупреждение", "Пожалуйста, сначала откройте файл конфигурации JSON.", parent=self)
            return
            
        logger.info("Запуск технической очистки тегов...")
        self.update()
        
        try:
            errors = report_builder.build_report(
                config=self.config,
                config_path=self.config_path,
                run_tables=False,
                run_charts=False,
                clean_tags=True,
                status_callback=lambda msg: (logger.info(msg), self.update())
            )
            
            if errors:
                err_msg = "\n".join(errors[:10])
                messagebox.showwarning("Очистка завершена с ошибками", f"Произошли ошибки при очистке тегов:\n\n{err_msg}", parent=self)
            else:
                logger.info("Техническая очистка успешно завершена.")
                messagebox.showinfo("Успех", f"Техническая очистка успешно завершена!\nВсе оставшиеся теги удалены из:\n{self.config.output_path or 'result.docx'}", parent=self)
        except Exception as e:
            logger.error(f"Сбой при технической очистке: {e}")
            messagebox.showerror("Ошибка очистки", f"Процесс завершился сбоем:\n{e}", parent=self)
