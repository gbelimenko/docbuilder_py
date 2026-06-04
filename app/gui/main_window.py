import os
import sys
import logging
import tkinter
from tkinter import messagebox, filedialog
import customtkinter

from app.models.config import ReportConfig
from app.services import config_loader, report_builder
from app.gui.tables_window import TablesWindow
from app.gui.charts_window import ChartsWindow
from app.gui.tags_window import TagsWindow
from app.gui.widgets.log_viewer import LogViewer

logger = logging.getLogger("DocBuilder.MainWindow")

class ActionCard(customtkinter.CTkFrame):
    def __init__(self, title, description, command=None, color_theme="blue", parent=None):
        super().__init__(parent, fg_color="#18181b", border_width=1, border_color="#27272a", corner_radius=8)
        self.command = command
        self.color_theme = color_theme
        self.is_dark = True
        
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

        # Bind hover and click events to everything inside the card
        for widget in [self, self.lbl_title, self.lbl_desc]:
            widget.bind("<Button-1>", self.on_click)
            widget.bind("<Enter>", self.on_enter)
            widget.bind("<Leave>", self.on_leave)

    def update_style(self, is_dark):
        self.is_dark = is_dark
        if is_dark:
            bg = "#18181b"
            border = "#27272a"
            desc_color = "#a1a1aa"
            
            if self.color_theme == "blue":
                self.title_color = "#38bdf8"
            elif self.color_theme == "purple":
                self.title_color = "#c084fc"
            elif self.color_theme == "amber":
                self.title_color = "#fbbf24"
            elif self.color_theme == "red":
                self.title_color = "#f87171"
        else:
            bg = "#ffffff"
            border = "#e4e4e7"
            desc_color = "#71717a"
            
            if self.color_theme == "blue":
                self.title_color = "#0284c7"
            elif self.color_theme == "purple":
                self.title_color = "#7c3aed"
            elif self.color_theme == "amber":
                self.title_color = "#b45309"
            elif self.color_theme == "red":
                self.title_color = "#dc2626"
                
        self.configure(fg_color=bg, border_color=border)
        self.lbl_title.configure(text_color=self.title_color)
        self.lbl_desc.configure(text_color=desc_color)

    def on_enter(self, event=None):
        if self.is_dark:
            self.configure(fg_color="#27272a", border_color="#3f3f46")
        else:
            self.configure(fg_color="#f4f4f5", border_color="#cbd5e1")

    def on_leave(self, event=None):
        if self.is_dark:
            self.configure(fg_color="#18181b", border_color="#27272a")
        else:
            self.configure(fg_color="#ffffff", border_color="#e4e4e7")

    def on_click(self, event=None):
        if self.command:
            self.command()


class MainWindow(customtkinter.CTk):
    def __init__(self):
        super().__init__()
        self.title("DocBuilder_v2.0 | Главная")
        self.geometry("1200x780")
        
        self.config = ReportConfig()
        self.config_path = ""
        self.is_dark_theme = True
        
        self.init_ui()
        self.apply_theme()
        
        logger.info("Программа запущена.")

    def init_ui(self):
        # Grid layout (Left panel column 0, Right panel column 1)
        self.grid_columnconfigure(0, weight=25, minsize=260)
        self.grid_columnconfigure(1, weight=75, minsize=940)
        self.grid_rowconfigure(0, weight=1)

        # =====================================================================
        # 1. LEFT PANEL (Tag List & Toolbar)
        # =====================================================================
        self.left_panel = customtkinter.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)
        self.left_panel.grid_columnconfigure(0, weight=1)
        self.left_panel.grid_rowconfigure(2, weight=1)

        # Left Top Toolbar
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

        # Search input for tag filtering
        self.search_input = customtkinter.CTkEntry(self.left_panel, placeholder_text="Поиск тегов...")
        self.search_input.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        self.search_input.bind("<KeyRelease>", self.filter_tags)

        # Tag List Container (Listbox + Scrollbar)
        list_container = customtkinter.CTkFrame(self.left_panel, fg_color="transparent")
        list_container.grid(row=2, column=0, sticky="nsew")
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

        # =====================================================================
        # 2. RIGHT PANEL (Logs, Info, Buttons Grid)
        # =====================================================================
        self.right_panel = customtkinter.CTkFrame(self, corner_radius=0, fg_color="transparent")
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

        self.lbl_info_config = customtkinter.CTkLabel(
            self.info_panel, text="Файл настроек: (Конфигурация не загружена)",
            font=("Segoe UI", 11, "bold"), text_color="#60a5fa"
        )
        self.lbl_info_config.grid(row=1, column=0, sticky="w", padx=15, pady=3)

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

        # Action Cards Grid
        buttons_grid_widget = customtkinter.CTkFrame(bottom_panel, fg_color="transparent")
        buttons_grid_widget.grid(row=0, column=1, sticky="nsew")
        buttons_grid_widget.grid_columnconfigure(0, weight=1)
        buttons_grid_widget.grid_columnconfigure(1, weight=1)
        buttons_grid_widget.grid_rowconfigure(0, weight=1)
        buttons_grid_widget.grid_rowconfigure(1, weight=1)

        self.btn_vert_articles = ActionCard(
            "Текстовые статьи", 
            "Просмотр и редактирование текстового наполнения отчета (топиков)", 
            command=self.open_tags_window, color_theme="amber", parent=buttons_grid_widget
        )
        self.btn_vert_articles.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)

        self.btn_vert_charts = ActionCard(
            "Диаграммы и графики", 
            "Импорт диаграмм из Excel в Word с точными размерами в пикселях", 
            command=self.open_charts_window, color_theme="purple", parent=buttons_grid_widget
        )
        self.btn_vert_charts.grid(row=0, column=1, sticky="nsew", padx=6, pady=6)

        self.btn_vert_tables = ActionCard(
            "Таблицы Excel", 
            "Сборка и верстка табличных диапазонов из Excel-листов", 
            command=self.open_tables_window, color_theme="blue", parent=buttons_grid_widget
        )
        self.btn_vert_tables.grid(row=1, column=0, sticky="nsew", padx=6, pady=6)

        self.btn_tech_clean = ActionCard(
            "Техническая очистка", 
            "Очистка Word-документа от всех неиспользованных тегов верстки", 
            command=self.run_technical_cleanup, color_theme="red", parent=buttons_grid_widget
        )
        self.btn_tech_clean.grid(row=1, column=1, sticky="nsew", padx=6, pady=6)

    def toggle_theme(self):
        self.is_dark_theme = not self.is_dark_theme
        if self.is_dark_theme:
            self.btn_theme.configure(text="☀️ СВЕТЛАЯ ТЕМА")
        else:
            self.btn_theme.configure(text="🌙 ТЕМНАЯ ТЕМА")
        self.apply_theme()

    def apply_theme(self):
        """Applies dark or light theme styles globally."""
        if self.is_dark_theme:
            customtkinter.set_appearance_mode("Dark")
            self.tags_list.configure(
                bg="#0c0c0e", fg="#e4e4e7", 
                selectbackground="#27272a", selectforeground="#3b82f6",
                highlightbackground="#1f1f24"
            )
            self.info_panel.configure(fg_color="#121218", border_color="#1a1a22")
            self.btn_word_open.configure(fg_color="#059669", hover_color="#047857")
        else:
            customtkinter.set_appearance_mode("Light")
            self.tags_list.configure(
                bg="#ffffff", fg="#18181b", 
                selectbackground="#e4e4e7", selectforeground="#2563eb",
                highlightbackground="#e4e4e7"
            )
            self.info_panel.configure(fg_color="#ffffff", border_color="#e4e4e7")
            self.btn_word_open.configure(fg_color="#10b981", hover_color="#059669")

        # Update action cards style
        for card in [self.btn_vert_articles, self.btn_vert_charts, self.btn_vert_tables, self.btn_tech_clean]:
            card.update_style(self.is_dark_theme)

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
        file_path = filedialog.askopenfilename(
            title="Выберите файл верстки Word",
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
        from app.utils.paths import resolve_dynamic_path
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
        
        self.edit_word_path.delete(0, "end")
        self.edit_word_path.insert(0, self.config.output_path)
        
        self.lbl_info_output.configure(text=f"Файл верстки: {self.config.output_path or '-'}")
        self.lbl_info_stats.configure(
            text=f"Загружено тегов: {len(self.config.tags)} | Таблиц: {len(self.config.tables)} | Диаграмм: {len(self.config.charts)}"
        )

    def filter_tags(self, event=None):
        query = self.search_input.get().lower().strip()
        self.tags_list.delete(0, "end")
        for tag in self.config.tags:
            if query in tag.lower():
                self.tags_list.insert("end", tag)

    def open_tables_window(self):
        if not self.config_path:
            messagebox.showwarning("Предупреждение", "Пожалуйста, сначала откройте файл конфигурации JSON.", parent=self)
            return
        logger.info("Открытие окна верстки таблиц.")
        dlg = TablesWindow(self.config, self.config_path, self)
        dlg.config_updated_connect(self.update_ui_from_config)
        self.wait_window(dlg)
        logger.info("Закрытие окна верстки таблиц.")

    def open_charts_window(self):
        if not self.config_path:
            messagebox.showwarning("Предупреждение", "Пожалуйста, сначала откройте файл конфигурации JSON.", parent=self)
            return
        logger.info("Открытие окна верстки диаграмм.")
        dlg = ChartsWindow(self.config, self.config_path, self)
        dlg.config_updated_connect(self.update_ui_from_config)
        self.wait_window(dlg)
        logger.info("Закрытие окна верстки диаграмм.")

    def open_tags_window(self):
        if not self.config_path:
            messagebox.showwarning("Предупреждение", "Пожалуйста, сначала откройте файл конфигурации JSON.", parent=self)
            return
        logger.info("Открытие списка тегов/статей.")
        dlg = TagsWindow(self.config, self.config_path, self)
        dlg.config_updated_connect(self.update_ui_from_config)
        self.wait_window(dlg)
        logger.info("Закрытие списка тегов/статей.")

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
