import os
import sys
import logging
import re
import tkinter
from tkinter import ttk, messagebox, filedialog
import customtkinter
import tempfile

from app.models.config import ReportConfig, TableItem, ChartItem, TopicItem
from app.services import config_loader
from app.utils.paths import resolve_dynamic_path

logger = logging.getLogger("DocBuilder.ConfigBuilder")

class ConfigBuilderWindow(customtkinter.CTkToplevel):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.title("DocBuilder | Настройка проекта и тегов (JSON)")
        self.geometry("1150x700")
        
        self.controller = controller
        self.config = controller.config
        self.config_path = controller.config_path
        self.preview_img = None

        self.init_ui()
        self.load_config_data()

        # Ensure popup window handles closing properly and stays on top
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_close(self):
        self.destroy()

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
        
        # Primary Action Buttons
        for btn in [self.btn_save_config, self.btn_grab, self.btn_copy_tag, self.btn_apply_tag]:
            btn.configure(
                fg_color=colors["primary"],
                hover_color=colors["primaryHover"],
                text_color="#ffffff"
            )
            
        # Standard Buttons
        standard_btns = [
            self.btn_add_manual, self.btn_del_tag, self.btn_load_prev,
            self.btn_link_browse, self.btn_open_json, self.btn_create_new,
            self.btn_close_cfg, self.btn_save_top
        ]
        for btn in standard_btns:
            btn.configure(
                fg_color=colors["surface2"],
                hover_color=colors["border"],
                text_color=colors["text"]
            )
            
        # Text fields
        text_entries = [
            self.entry_json_path, self.entry_word_path, self.entry_def_dir,
            self.tag_entry, self.link_entry, self.sheet_entry,
            self.range_a_entry, self.range_b_entry, self.chart_id_entry
        ]
        for entry in text_entries:
            entry.configure(
                fg_color=colors["surface"],
                border_color=colors["border"],
                text_color=colors["text"]
            )
            
        # OptionMenus & Textbox
        self.opt_accent.configure(
            fg_color=colors["surface2"],
            button_color=colors["surface2"],
            button_hover_color=colors["border"],
            text_color=colors["text"]
        )
        self.topic_textbox.configure(
            fg_color=colors["surface"],
            border_color=colors["border"],
            text_color=colors["text"]
        )
        
        # Checkboxes
        self.chk_use.configure(text_color=colors["text"])
        self.chk_hdr.configure(text_color=colors["text"])
        
        # Outer Containers/Frames
        self.middle_panel.configure(fg_color=colors["bg"], border_color=colors["border"])
        self.editor_box.configure(fg_color=colors["surface"], border_color=colors["border"])
        if hasattr(self, "cfg_box"):
            self.cfg_box.configure(fg_color=colors["surface"], border_color=colors["border"])
        if hasattr(self, "preview_container"):
            self.preview_container.configure(fg_color=colors["surface"], border_color=colors["border"])
            
        self.table_widget.tag_configure("odd", background=colors["surface"])
        self.table_widget.tag_configure("even", background=colors["surface2"])
        
        style = ttk.Style()
        style.configure("Treeview", 
                        background=colors["surface"], 
                        foreground=colors["text"], 
                        fieldbackground=colors["surface"],
                        bordercolor=colors["border"])
        style.map("Treeview", 
                  background=[("selected", colors["primarySoft"])], 
                  foreground=[("selected", colors["primary"])])

        self.preview_label.configure(text_color=colors["textSecondary"])

    def init_ui(self):
        # 3-column layout: Left (listbox), Middle (editors), Right (preview)
        self.grid_columnconfigure(0, weight=35, minsize=320)
        self.grid_columnconfigure(1, weight=45, minsize=480)
        self.grid_columnconfigure(2, weight=20, minsize=260)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)

        accent = self.get_accent_theme()

        # 0. Navigation / Action Toolbar (Row 0)
        toolbar_top = customtkinter.CTkFrame(self, fg_color="transparent")
        toolbar_top.grid(row=0, column=0, columnspan=3, sticky="ew", padx=12, pady=(8, 4))
        
        self.btn_open_json = customtkinter.CTkButton(
            toolbar_top, text="📂 Открыть JSON", width=120, height=28, 
            font=("Segoe UI", 11, "bold"), command=self.open_json_file
        )
        self.btn_open_json.pack(side="left", padx=(0, 6))

        self.btn_create_new = customtkinter.CTkButton(
            toolbar_top, text="📄 Создать новый", width=120, height=28, 
            font=("Segoe UI", 11, "bold"), command=self.create_new_config
        )
        self.btn_create_new.pack(side="left", padx=(0, 6))

        self.btn_close_cfg = customtkinter.CTkButton(
            toolbar_top, text="🚫 Закрыть конфиг", width=120, height=28, 
            font=("Segoe UI", 11, "bold"), command=self.close_config
        )
        self.btn_close_cfg.pack(side="left", padx=(0, 6))

        self.btn_save_top = customtkinter.CTkButton(
            toolbar_top, text="💾 Сохранить JSON", width=120, height=28, 
            font=("Segoe UI", 11, "bold"), command=self.save_config_to_disk
        )
        self.btn_save_top.pack(side="left", padx=(0, 6))

        # 1. Left Panel: Unified Multi-column Tags Grid & Controls
        left_panel = customtkinter.CTkFrame(self, fg_color="transparent")
        left_panel.grid(row=1, column=0, sticky="nsew", padx=12, pady=12)
        left_panel.grid_columnconfigure(0, weight=1)
        left_panel.grid_rowconfigure(1, weight=1)

        lbl_tags = customtkinter.CTkLabel(left_panel, text="Список всех тегов проекта:", font=("Segoe UI", 11, "bold"), text_color="#aaaaaa")
        lbl_tags.grid(row=0, column=0, sticky="w", pady=(0, 4))

        list_container = customtkinter.CTkFrame(left_panel, fg_color="transparent")
        list_container.grid(row=1, column=0, sticky="nsew", pady=(0, 8))
        list_container.grid_columnconfigure(0, weight=1)
        list_container.grid_rowconfigure(0, weight=1)

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
            list_container, 
            columns=("Tag", "Type", "Link", "Sheet", "RangeA_ChartId", "RangeB", "Use", "Header"),
            show="headings",
            selectmode="browse"
        )
        self.table_widget.grid(row=0, column=0, sticky="nsew")

        scrollbar = customtkinter.CTkScrollbar(list_container, orientation="vertical", command=self.table_widget.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.table_widget.configure(yscrollcommand=scrollbar.set)

        self.table_widget.heading("Tag", text="Tag")
        self.table_widget.heading("Type", text="Тип")
        self.table_widget.heading("Link", text="Файл")
        self.table_widget.heading("Sheet", text="Лист")
        self.table_widget.heading("RangeA_ChartId", text="Коорд/ID")
        self.table_widget.heading("RangeB", text="Коорд Б")
        self.table_widget.heading("Use", text="Use")
        self.table_widget.heading("Header", text="Hdr")

        self.table_widget.column("Tag", width=95, anchor="w")
        self.table_widget.column("Type", width=55, anchor="center")
        self.table_widget.column("Link", width=70, anchor="w")
        self.table_widget.column("Sheet", width=60, anchor="w")
        self.table_widget.column("RangeA_ChartId", width=55, anchor="center")
        self.table_widget.column("RangeB", width=50, anchor="center")
        self.table_widget.column("Use", width=35, anchor="center")
        self.table_widget.column("Header", width=35, anchor="center")

        self.table_widget.bind("<<TreeviewSelect>>", self.tag_selection_changed)

        left_toolbar = customtkinter.CTkFrame(left_panel, fg_color="transparent")
        left_toolbar.grid(row=2, column=0, sticky="ew")

        self.btn_grab = customtkinter.CTkButton(
            left_toolbar, text="⚡ Захватить из Excel", height=32,
            font=("Segoe UI", 11, "bold"), fg_color=accent["fg"], hover_color=accent["hover"],
            command=self.grab_from_excel
        )
        self.btn_grab.pack(fill="x", pady=(0, 6))

        btn_row2 = customtkinter.CTkFrame(left_toolbar, fg_color="transparent")
        btn_row2.pack(fill="x")
        
        self.btn_add_manual = customtkinter.CTkButton(
            btn_row2, text="+ Вручную", height=28, width=100, font=("Segoe UI", 10), command=self.add_tag_manual
        )
        self.btn_add_manual.pack(side="left", fill="x", expand=True, padx=(0, 2))

        self.btn_del_tag = customtkinter.CTkButton(
            btn_row2, text="❌ Удалить", height=28, width=100, font=("Segoe UI", 10), fg_color="#552222", hover_color="#773333", command=self.delete_selected_tag
        )
        self.btn_del_tag.pack(side="right", fill="x", expand=True, padx=(2, 0))

        # 2. Middle Panel: Config Settings & Selected Item Editors
        self.middle_panel = customtkinter.CTkScrollableFrame(self, fg_color="#141416", border_width=1, border_color="#27272a")
        self.middle_panel.grid(row=1, column=1, sticky="nsew", padx=6, pady=12)
        self.middle_panel.grid_columnconfigure(0, weight=1)

        # Config Files Settings Block
        lbl_cfg_section = customtkinter.CTkLabel(self.middle_panel, text="Настройки проекта (JSON):", font=("Segoe UI", 12, "bold"), text_color="#3b82f6")
        lbl_cfg_section.grid(row=0, column=0, sticky="w", padx=10, pady=(8, 4))

        self.cfg_box = customtkinter.CTkFrame(self.middle_panel, fg_color="#1c1c1f", border_width=1, border_color="#2d2d30")
        self.cfg_box.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 12))
        self.cfg_box.grid_columnconfigure(1, weight=1)

        # JSON Path
        customtkinter.CTkLabel(self.cfg_box, text="Файл JSON:").grid(row=0, column=0, padx=8, pady=4, sticky="e")
        self.entry_json_path = customtkinter.CTkEntry(self.cfg_box, font=("Segoe UI", 11))
        self.entry_json_path.grid(row=0, column=1, sticky="ew", padx=4, pady=4)
        
        # Word Template Path
        customtkinter.CTkLabel(self.cfg_box, text="Файл Word:").grid(row=1, column=0, padx=8, pady=4, sticky="e")
        self.entry_word_path = customtkinter.CTkEntry(self.cfg_box, font=("Segoe UI", 11))
        self.entry_word_path.grid(row=1, column=1, sticky="ew", padx=4, pady=4)

        # Default Word Folder
        customtkinter.CTkLabel(self.cfg_box, text="Дефолт. папка:").grid(row=2, column=0, padx=8, pady=4, sticky="e")
        self.entry_def_dir = customtkinter.CTkEntry(self.cfg_box, font=("Segoe UI", 11))
        self.entry_def_dir.grid(row=2, column=1, sticky="ew", padx=4, pady=4)

        # Accent Theme
        customtkinter.CTkLabel(self.cfg_box, text="Цвет темы:").grid(row=3, column=0, padx=8, pady=4, sticky="e")
        self.opt_accent = customtkinter.CTkOptionMenu(self.cfg_box, values=["blue", "emerald", "rose", "amber", "purple"], command=self.change_accent_from_ui)
        self.opt_accent.grid(row=3, column=1, sticky="w", padx=4, pady=8)

        # Separator line
        sep = customtkinter.CTkFrame(self.middle_panel, height=2, fg_color="#2d2d30")
        sep.grid(row=2, column=0, sticky="ew", padx=10, pady=6)

        # Tag Editor Block
        self.lbl_editor_section = customtkinter.CTkLabel(self.middle_panel, text="Свойства выбранного тега:", font=("Segoe UI", 12, "bold"), text_color="#aaaaaa")
        self.lbl_editor_section.grid(row=3, column=0, sticky="w", padx=10, pady=4)

        # Active Editor Container Frame
        self.editor_box = customtkinter.CTkFrame(self.middle_panel, fg_color="#1c1c1f", border_width=1, border_color="#2d2d30")
        self.editor_box.grid(row=4, column=0, sticky="ew", padx=10, pady=(0, 12))
        self.editor_box.grid_columnconfigure(1, weight=1)

        # Placeholder label when no tag is selected
        self.lbl_no_tag = customtkinter.CTkLabel(self.editor_box, text="Выберите тег для редактирования", font=("Segoe UI", 11, "italic"), text_color="#777777")
        self.lbl_no_tag.pack(padx=20, pady=40)

        # Editor UI Widgets (initialized but hidden)
        self._init_sub_editors()

        # Footer Button
        self.btn_save_config = customtkinter.CTkButton(
            self.middle_panel, text="СОХРАНИТЬ ИЗМЕНЕНИЯ JSON", height=38,
            font=("Segoe UI", 13, "bold"), fg_color=accent["fg"], hover_color=accent["hover"],
            command=self.save_config_to_disk
        )
        self.btn_save_config.grid(row=5, column=0, sticky="ew", padx=10, pady=15)

        # 3. Right Panel: Preview Area
        right_panel = customtkinter.CTkFrame(self, fg_color="transparent")
        right_panel.grid(row=1, column=2, sticky="nsew", padx=12, pady=12)
        right_panel.grid_columnconfigure(0, weight=1)
        right_panel.grid_rowconfigure(1, weight=1)

        lbl_preview = customtkinter.CTkLabel(right_panel, text="Предпросмотр Excel:", font=("Segoe UI", 11, "bold"), text_color="#aaaaaa")
        lbl_preview.grid(row=0, column=0, sticky="w", pady=(0, 4))

        self.preview_container = customtkinter.CTkFrame(right_panel, fg_color="#0d0d0f", border_width=1, border_color="#27272a")
        self.preview_container.grid(row=1, column=0, sticky="nsew", pady=(0, 8))
        self.preview_container.grid_columnconfigure(0, weight=1)
        self.preview_container.grid_rowconfigure(0, weight=1)

        # Label inside frame to display images
        self.preview_label = customtkinter.CTkLabel(
            self.preview_container, text="Выберите тег табличного\nдиапазона или графика\nдля вывода картинки.",
            font=("Segoe UI", 11, "italic"), text_color="#666666", wraplength=220
        )
        self.preview_label.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)

        # Controls under preview
        self.btn_load_prev = customtkinter.CTkButton(
            right_panel, text="👁️ Загрузить превью из Excel", height=32, font=("Segoe UI", 11),
            fg_color="#333333", hover_color="#444444", command=self.load_preview
        )
        self.btn_load_prev.grid(row=2, column=0, sticky="ew", pady=(0, 6))

        self.btn_copy_tag = customtkinter.CTkButton(
            right_panel, text="📋 Скопировать тег", height=34, font=("Segoe UI", 11, "bold"),
            fg_color=accent["fg"], hover_color=accent["hover"], command=self.copy_selected_tag
        )
        self.btn_copy_tag.grid(row=3, column=0, sticky="ew")

    def _init_sub_editors(self):
        # We will dynamically pack/grid these depending on selection
        self.editor_fields = customtkinter.CTkFrame(self.editor_box, fg_color="transparent")
        self.editor_fields.grid_columnconfigure(1, weight=1)

        # General Tag input (all types)
        customtkinter.CTkLabel(self.editor_fields, text="Имя тега:").grid(row=0, column=0, padx=8, pady=6, sticky="e")
        self.tag_entry = customtkinter.CTkEntry(self.editor_fields, font=("Segoe UI", 11))
        self.tag_entry.grid(row=0, column=1, sticky="ew", padx=4, pady=6)

        # Excel File Link (Table/Chart)
        self.lbl_link = customtkinter.CTkLabel(self.editor_fields, text="Excel файл:")
        self.lbl_link.grid(row=1, column=0, padx=8, pady=6, sticky="e")
        
        self.link_frame = customtkinter.CTkFrame(self.editor_fields, fg_color="transparent")
        self.link_frame.grid(row=1, column=1, sticky="ew")
        self.link_frame.grid_columnconfigure(0, weight=1)
        
        self.link_entry = customtkinter.CTkEntry(self.link_frame, font=("Segoe UI", 11))
        self.link_entry.grid(row=0, column=0, sticky="ew", padx=(4, 2), pady=0)
        
        self.btn_link_browse = customtkinter.CTkButton(self.link_frame, text="...", width=28, height=28, command=self.browse_link_path)
        self.btn_link_browse.grid(row=0, column=1, padx=(2, 4), pady=0)

        # Sheet Name (Table/Chart)
        self.lbl_sheet = customtkinter.CTkLabel(self.editor_fields, text="Имя листа:")
        self.lbl_sheet.grid(row=2, column=0, padx=8, pady=6, sticky="e")
        self.sheet_entry = customtkinter.CTkEntry(self.editor_fields, font=("Segoe UI", 11))
        self.sheet_entry.grid(row=2, column=1, sticky="w", padx=4, pady=6, width=160)

        # Range coordinates A / B (Table only)
        self.lbl_range_a = customtkinter.CTkLabel(self.editor_fields, text="Начало (А):")
        self.lbl_range_a.grid(row=3, column=0, padx=8, pady=6, sticky="e")
        self.range_a_entry = customtkinter.CTkEntry(self.editor_fields, font=("Segoe UI", 11))
        self.range_a_entry.grid(row=3, column=1, sticky="w", padx=4, pady=6, width=100)

        self.lbl_range_b = customtkinter.CTkLabel(self.editor_fields, text="Конец (Б):")
        self.lbl_range_b.grid(row=4, column=0, padx=8, pady=6, sticky="e")
        self.range_b_entry = customtkinter.CTkEntry(self.editor_fields, font=("Segoe UI", 11))
        self.range_b_entry.grid(row=4, column=1, sticky="w", padx=4, pady=6, width=100)

        # Use and Header Checkboxes (Table only)
        self.use_var = tkinter.BooleanVar(value=True)
        self.chk_use = customtkinter.CTkCheckBox(self.editor_fields, text="Использовать в отчете", variable=self.use_var, font=("Segoe UI", 11))
        self.chk_use.grid(row=5, column=1, sticky="w", padx=4, pady=4)

        self.hdr_var = tkinter.BooleanVar(value=False)
        self.chk_hdr = customtkinter.CTkCheckBox(self.editor_fields, text="Заголовочная строка", variable=self.hdr_var, font=("Segoe UI", 11))
        self.chk_hdr.grid(row=6, column=1, sticky="w", padx=4, pady=4)

        # Chart ID (Chart only)
        self.lbl_chart_id = customtkinter.CTkLabel(self.editor_fields, text="ID графика:")
        self.lbl_chart_id.grid(row=7, column=0, padx=8, pady=6, sticky="e")
        self.chart_id_entry = customtkinter.CTkEntry(self.editor_fields, font=("Segoe UI", 11))
        self.chart_id_entry.grid(row=7, column=1, sticky="w", padx=4, pady=6, width=100)

        # Topic text editor (Topic only)
        self.lbl_topic_text = customtkinter.CTkLabel(self.editor_fields, text="Текст топика:")
        self.lbl_topic_text.grid(row=8, column=0, padx=8, pady=6, sticky="ne")
        self.topic_textbox = customtkinter.CTkTextbox(self.editor_fields, height=120, font=("Segoe UI", 11), fg_color="#121214", border_width=1, border_color="#2b2b2e")
        self.topic_textbox.grid(row=8, column=1, sticky="ew", padx=4, pady=6)

        # Apply Tag Changes Button (all types)
        self.btn_apply_tag = customtkinter.CTkButton(
            self.editor_fields, text="Применить свойства к тегу", height=32, font=("Segoe UI", 11, "bold"),
            command=self.apply_tag_changes
        )
        self.btn_apply_tag.grid(row=9, column=0, columnspan=2, sticky="ew", padx=4, pady=12)

    def load_config_data(self):
        self.refresh_theme_colors()
        
        # Populate config global details
        self.entry_json_path.delete(0, "end")
        self.entry_json_path.insert(0, self.config_path or "")

        self.entry_word_path.delete(0, "end")
        self.entry_word_path.insert(0, self.config.output_path or "")

        self.entry_def_dir.delete(0, "end")
        self.entry_def_dir.insert(0, self.config.default_word_dir or "")

        # Set accent opt dropdown
        accent_val = getattr(self.config, "accent_color", "blue") or "blue"
        if accent_val in ["blue", "emerald", "rose", "amber", "purple"]:
            self.opt_accent.set(accent_val)
        else:
            self.opt_accent.set("blue")

        # Clear treeview
        for item in self.table_widget.get_children():
            self.table_widget.delete(item)

        # Populate Tables
        for item in self.config.tables:
            self.table_widget.insert("", "end", values=(
                item.tag,
                "Таблица",
                item.excel_path,
                item.sheet,
                item.range_a,
                item.range_b,
                "Да" if item.use else "Нет",
                "Да" if item.header else "Нет"
            ))

        # Populate Charts
        for item in self.config.charts:
            self.table_widget.insert("", "end", values=(
                item.tag,
                "График",
                item.excel_path,
                item.sheet,
                str(item.chart_id),
                "",
                "",
                ""
            ))

        # Populate Topics
        for item in self.config.topics:
            self.table_widget.insert("", "end", values=(
                item.tag,
                "Статья",
                "",
                "",
                "",
                "",
                "",
                ""
            ))

        # Populate other tags
        known_tags = set(t.tag for t in self.config.tables) | set(c.tag for c in self.config.charts) | set(tp.tag for tp in self.config.topics)
        for tag in self.config.tags:
            if tag not in known_tags:
                self.table_widget.insert("", "end", values=(
                    tag,
                    "Тег",
                    "",
                    "",
                    "",
                    "",
                    "",
                    ""
                ))

        # Clear editor and previews
        self.lbl_no_tag.pack(padx=20, pady=40)
        self.editor_fields.grid_forget()
        self.preview_label.configure(image="", text="Выберите тег табличного\nдиапазона или графика\nдля вывода картинки.")

    def change_accent_from_ui(self, val):
        self.config.accent_color = val
        
        # Sync uiTheme accent
        THEME_ACCENTS = {
            "blue": "#3b82f6",
            "emerald": "#10b981",
            "rose": "#f43f5e",
            "amber": "#f59e0b",
            "purple": "#8b5cf6"
        }
        if getattr(self.config, "uiTheme", None) is None:
            from app.models.config import UITheme
            self.config.uiTheme = UITheme()
            
        self.config.uiTheme.accent = THEME_ACCENTS.get(val.lower(), "#3b82f6")
        
        self.refresh_theme_colors()
        # Notify controller if needed
        if hasattr(self.controller, "config"):
            self.controller.config.accent_color = val
            self.controller.config.uiTheme = self.config.uiTheme
            if hasattr(self.controller, "apply_theme"):
                self.controller.apply_theme()

    def tag_selection_changed(self, event=None):
        selection = self.table_widget.selection()
        if not selection:
            self.lbl_no_tag.pack(padx=20, pady=40)
            self.editor_fields.grid_forget()
            return

        self.lbl_no_tag.pack_forget()
        self.editor_fields.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)

        values = self.table_widget.item(selection[0])["values"]
        tag_name = str(values[0]).strip()
        tag_type = str(values[1]).strip()

        self.lbl_editor_section.configure(text=f"Свойства тега: {tag_name} ({tag_type})")
        self.preview_label.configure(image="", text="Нажмите кнопку ниже,\nчтобы загрузить изображение.")

        self.tag_entry.delete(0, "end")
        self.tag_entry.insert(0, tag_name)

        if tag_type == "Таблица":
            self.lbl_link.grid()
            self.link_frame.grid()
            self.lbl_sheet.grid()
            self.sheet_entry.grid()
            self.lbl_range_a.grid()
            self.range_a_entry.grid()
            self.lbl_range_b.grid()
            self.range_b_entry.grid()
            self.chk_use.grid()
            self.chk_hdr.grid()
            
            self.lbl_chart_id.grid_remove()
            self.chart_id_entry.grid_remove()
            self.lbl_topic_text.grid_remove()
            self.topic_textbox.grid_remove()

            self.link_entry.delete(0, "end")
            self.link_entry.insert(0, values[2])
            self.sheet_entry.delete(0, "end")
            self.sheet_entry.insert(0, values[3])
            self.range_a_entry.delete(0, "end")
            self.range_a_entry.insert(0, values[4])
            self.range_b_entry.delete(0, "end")
            self.range_b_entry.insert(0, values[5])
            self.use_var.set(values[6] == "Да")
            self.chk_use.select() if values[6] == "Да" else self.chk_use.deselect()
            self.hdr_var.set(values[7] == "Да")
            self.chk_hdr.select() if values[7] == "Да" else self.chk_hdr.deselect()

        elif tag_type == "График":
            self.lbl_link.grid()
            self.link_frame.grid()
            self.lbl_sheet.grid()
            self.sheet_entry.grid()
            self.lbl_chart_id.grid()
            self.chart_id_entry.grid()
            
            self.lbl_range_a.grid_remove()
            self.range_a_entry.grid_remove()
            self.lbl_range_b.grid_remove()
            self.range_b_entry.grid_remove()
            self.chk_use.grid_remove()
            self.chk_hdr.grid_remove()
            self.lbl_topic_text.grid_remove()
            self.topic_textbox.grid_remove()

            self.link_entry.delete(0, "end")
            self.link_entry.insert(0, values[2])
            self.sheet_entry.delete(0, "end")
            self.sheet_entry.insert(0, values[3])
            self.chart_id_entry.delete(0, "end")
            self.chart_id_entry.insert(0, str(values[4]))

        elif tag_type == "Статья":
            self.lbl_topic_text.grid()
            self.topic_textbox.grid()

            self.lbl_link.grid_remove()
            self.link_frame.grid_remove()
            self.lbl_sheet.grid_remove()
            self.sheet_entry.grid_remove()
            self.lbl_range_a.grid_remove()
            self.range_a_entry.grid_remove()
            self.lbl_range_b.grid_remove()
            self.range_b_entry.grid_remove()
            self.chk_use.grid_remove()
            self.chk_hdr.grid_remove()
            self.lbl_chart_id.grid_remove()
            self.chart_id_entry.grid_remove()

            item = next((x for x in self.config.topics if x.tag == tag_name), None)
            self.topic_textbox.delete("1.0", "end")
            if item and item.text:
                self.topic_textbox.insert("1.0", item.text)

        else:
            self.lbl_link.grid_remove()
            self.link_frame.grid_remove()
            self.lbl_sheet.grid_remove()
            self.sheet_entry.grid_remove()
            self.lbl_range_a.grid_remove()
            self.range_a_entry.grid_remove()
            self.lbl_range_b.grid_remove()
            self.range_b_entry.grid_remove()
            self.chk_use.grid_remove()
            self.chk_hdr.grid_remove()
            self.lbl_chart_id.grid_remove()
            self.chart_id_entry.grid_remove()
            self.lbl_topic_text.grid_remove()
            self.topic_textbox.grid_remove()

    def apply_tag_changes(self):
        selection = self.table_widget.selection()
        if not selection:
            return

        old_values = self.table_widget.item(selection[0])["values"]
        old_tag = str(old_values[0]).strip()
        tag_type = str(old_values[1]).strip()
        new_tag = self.tag_entry.get().strip()

        if not new_tag:
            messagebox.showwarning("Ошибка", "Имя тега не может быть пустым.", parent=self)
            return

        if old_tag in self.config.tags:
            tags_idx = self.config.tags.index(old_tag)
            self.config.tags[tags_idx] = new_tag
        else:
            self.config.tags.append(new_tag)

        if tag_type == "Таблица":
            item = next((x for x in self.config.tables if x.tag == old_tag), None)
            excel_path = self.link_entry.get().strip()
            sheet = self.sheet_entry.get().strip()
            range_a = self.range_a_entry.get().strip()
            range_b = self.range_b_entry.get().strip()
            use = self.use_var.get()
            header = self.hdr_var.get()
            
            if item:
                item.tag = new_tag
                item.excel_path = excel_path
                item.sheet = sheet
                item.range_a = range_a
                item.range_b = range_b
                item.use = use
                item.header = header
            else:
                self.config.tables.append(TableItem(
                    tag=new_tag, excel_path=excel_path, sheet=sheet,
                    range_a=range_a, range_b=range_b, use=use, header=header
                ))
            
            self.table_widget.item(selection[0], values=(
                new_tag, tag_type, excel_path, sheet, range_a, range_b,
                "Да" if use else "Нет", "Да" if header else "Нет"
            ))

        elif tag_type == "График":
            item = next((x for x in self.config.charts if x.tag == old_tag), None)
            excel_path = self.link_entry.get().strip()
            sheet = self.sheet_entry.get().strip()
            chart_id_str = self.chart_id_entry.get().strip()
            try:
                chart_id = int(chart_id_str)
            except ValueError:
                chart_id = 1
                
            if item:
                item.tag = new_tag
                item.excel_path = excel_path
                item.sheet = sheet
                item.chart_id = chart_id
            else:
                self.config.charts.append(ChartItem(
                    tag=new_tag, excel_path=excel_path, sheet=sheet, chart_id=chart_id
                ))
                
            self.table_widget.item(selection[0], values=(
                new_tag, tag_type, excel_path, sheet, str(chart_id), "", "", ""
            ))

        elif tag_type == "Статья":
            item = next((x for x in self.config.topics if x.tag == old_tag), None)
            text_val = self.topic_textbox.get("1.0", "end").strip()
            if item:
                item.tag = new_tag
                item.text = text_val
            else:
                self.config.topics.append(TopicItem(tag=new_tag, text=text_val))
                
            self.table_widget.item(selection[0], values=(
                new_tag, tag_type, "", "", "", "", "", ""
            ))
            
        else:
            self.table_widget.item(selection[0], values=(
                new_tag, tag_type, "", "", "", "", "", ""
            ))

        logger.info(f"Tag changes applied: {old_tag} -> {new_tag}")

    def add_tag_manual(self):
        dialog = customtkinter.CTkInputDialog(text="Введите тип тега (table / chart / topic):", title="Создание тега")
        ans = dialog.get_input()
        if not ans:
            return
            
        ans = ans.lower().strip()
        if "table" in ans or "таб" in ans:
            max_num = 0
            for tag in self.config.tags:
                if tag.startswith("<TableTag_"):
                    num = re.search(r'\d+', tag)
                    if num: max_num = max(max_num, int(num.group(0)))
            new_tag = f"<TableTag_{max_num + 1}>"
            self.config.tables.append(TableItem(tag=new_tag, excel_path="", sheet="Sheet1", range_a="A1", range_b="", use=True, header=False))
            self.config.tags.append(new_tag)
            
            new_row_id = self.table_widget.insert("", "end", values=(
                new_tag, "Таблица", "", "Sheet1", "A1", "", "Да", "Нет"
            ))
        elif "chart" in ans or "граф" in ans:
            max_num = 0
            for tag in self.config.tags:
                if tag.startswith("<ChartTag_"):
                    num = re.search(r'\d+', tag)
                    if num: max_num = max(max_num, int(num.group(0)))
            new_tag = f"<ChartTag_{max_num + 1}>"
            self.config.charts.append(ChartItem(tag=new_tag, excel_path="", sheet="Sheet1", chart_id=1))
            self.config.tags.append(new_tag)
            
            new_row_id = self.table_widget.insert("", "end", values=(
                new_tag, "График", "", "Sheet1", "1", "", "", ""
            ))
        else:
            new_tag = f"<TOPIC_New>"
            self.config.topics.append(TopicItem(tag=new_tag, text=""))
            self.config.tags.append(new_tag)
            
            new_row_id = self.table_widget.insert("", "end", values=(
                new_tag, "Статья", "", "", "", "", "", ""
            ))
            
        self.table_widget.selection_set(new_row_id)
        self.table_widget.see(new_row_id)
        self.tag_selection_changed()

    def delete_selected_tag(self):
        selection = self.table_widget.selection()
        if not selection:
            return

        values = self.table_widget.item(selection[0])["values"]
        tag_name = str(values[0]).strip()
        tag_type = str(values[1]).strip()

        confirm = messagebox.askyesno("Удаление", f"Удалить тег {tag_name} из конфигурации?", parent=self)
        if confirm:
            if tag_name in self.config.tags:
                self.config.tags.remove(tag_name)
                
            if tag_type == "Таблица":
                self.config.tables = [x for x in self.config.tables if x.tag != tag_name]
            elif tag_type == "График":
                self.config.charts = [x for x in self.config.charts if x.tag != tag_name]
            elif tag_type == "Статья":
                self.config.topics = [x for x in self.config.topics if x.tag != tag_name]

            self.table_widget.delete(selection[0])
            self.tag_entry.delete(0, "end")
            self.link_entry.delete(0, "end")
            self.sheet_entry.delete(0, "end")
            self.range_a_entry.delete(0, "end")
            self.range_b_entry.delete(0, "end")
            self.chart_id_entry.delete(0, "end")
            self.topic_textbox.delete("1.0", "end")
            self.lbl_no_tag.pack(padx=20, pady=40)
            self.editor_fields.grid_forget()

    def grab_from_excel(self):
        if sys.platform != "win32":
            messagebox.showwarning(
                "Не поддерживается", 
                "Захват данных из Excel поддерживается только на ОС Windows с установленным Excel.", 
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
            
            if active_chart is not None:
                chart_shape = active_chart.Parent
                ws = chart_shape.Parent
                wb = ws.Parent

                excel_path = wb.FullName
                sheet_name = ws.Name
                chart_name = chart_shape.Name
                
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

                max_num = 0
                for tag in self.config.tags:
                    if tag.startswith("<ChartTag_"):
                        num = re.search(r'\d+', tag)
                        if num: max_num = max(max_num, int(num.group(0)))
                new_tag = f"<ChartTag_{max_num + 1}>"

                self.config.charts.append(ChartItem(
                    tag=new_tag,
                    excel_path=excel_path,
                    sheet=sheet_name,
                    chart_id=chart_id
                ))
                self.config.tags.append(new_tag)

                new_row_id = self.table_widget.insert("", "end", values=(
                    new_tag, "График", excel_path, sheet_name, str(chart_id), "", "", ""
                ))

                self.table_widget.selection_set(new_row_id)
                self.table_widget.see(new_row_id)
                self.tag_selection_changed()

                self.copy_text_to_clipboard(new_tag)
                self.load_preview()

                messagebox.showinfo(
                    "Успешный захват графика",
                    f"Добавлен график № {chart_id} на листе '{sheet_name}'.\n\n"
                    f"Создан новый тег: {new_tag} (скопирован в буфер обмена!).",
                    parent=self
                )
                return

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

            max_num = 0
            for tag in self.config.tags:
                if tag.startswith("<TableTag_"):
                    num = re.search(r'\d+', tag)
                    if num: max_num = max(max_num, int(num.group(0)))
            new_tag = f"<TableTag_{max_num + 1}>"

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

            new_row_id = self.table_widget.insert("", "end", values=(
                new_tag, "Таблица", excel_path, sheet_name, range_a, range_b, "Да", "Нет"
            ))

            self.table_widget.selection_set(new_row_id)
            self.table_widget.see(new_row_id)
            self.tag_selection_changed()

            self.copy_text_to_clipboard(new_tag)
            self.load_preview()

            messagebox.showinfo(
                "Успешный захват таблицы",
                f"Добавлен диапазон {range_a}:{range_b} на листе '{sheet_name}'.\n\n"
                f"Создан новый тег: {new_tag} (скопирован в буфер обмена!).",
                parent=self
            )

        except Exception as e:
            messagebox.showerror("Ошибка импорта", f"Не удалось считать выделение из Excel:\n{e}", parent=self)

    def load_preview(self):
        selection = self.table_widget.selection()
        if not selection:
            return

        values = self.table_widget.item(selection[0])["values"]
        tag_name = str(values[0]).strip()
        tag_type = str(values[1]).strip()

        self.preview_label.configure(image="", text="Загрузка превью из Excel...")
        self.update()

        if sys.platform != "win32":
            self.preview_label.configure(text="Предпросмотр доступен только на Windows")
            return

        try:
            import win32com.client
            is_table = (tag_type == "Таблица")
            is_chart = (tag_type == "График")

            if is_table:
                excel_path = str(values[2]).strip()
                sheet = str(values[3]).strip()
                range_a = str(values[4]).strip()
                range_b = str(values[5]).strip()
            elif is_chart:
                excel_path = str(values[2]).strip()
                sheet = str(values[3]).strip()
                chart_id_str = str(values[4]).strip()
            else:
                self.preview_label.configure(text="Предпросмотр для топиков не поддерживается")
                return

            if not excel_path:
                self.preview_label.configure(text="Путь к Excel не заполнен")
                return

            resolved_path = resolve_dynamic_path(excel_path, self.config_path)
            if not os.path.exists(resolved_path):
                self.preview_label.configure(text=f"Файл Excel не найден:\n{excel_path}")
                return

            try:
                excel = win32com.client.GetActiveObject("Excel.Application")
            except Exception:
                self.preview_label.configure(text="Excel не запущен")
                return

            wb = None
            for open_wb in excel.Workbooks:
                if os.path.normpath(open_wb.FullName).lower() == os.path.normpath(resolved_path).lower():
                    wb = open_wb
                    break

            if wb is None:
                wb = excel.Workbooks.Open(resolved_path, ReadOnly=True)

            try:
                ws = wb.Worksheets(sheet)
            except Exception:
                self.preview_label.configure(text=f"Лист '{sheet}' не найден в файле")
                return

            temp_dir = tempfile.gettempdir()
            clean_tag_name = re.sub(r'[^a-zA-Z0-9_]', '_', tag_name)
            temp_path = os.path.join(temp_dir, f"docbuilder_prev_{clean_tag_name}.png")

            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

            if is_chart:
                try:
                    try:
                        idx = int(chart_id_str)
                        chart_obj = ws.ChartObjects(idx)
                    except Exception:
                        chart_obj = ws.ChartObjects(chart_id_str)
                    chart_obj.Chart.Export(temp_path, "PNG")
                except Exception as ex:
                    self.preview_label.configure(text=f"Не удалось экспортировать график:\n{ex}")
                    return
            else:
                try:
                    addr = range_a
                    if range_b:
                        addr += f":{range_b}"
                    rng = ws.Range(addr)
                    
                    rng.Copy()
                    
                    temp_chart = ws.ChartObjects().Add(0, 0, rng.Width, rng.Height)
                    temp_chart.Chart.Paste()
                    temp_chart.Chart.Export(temp_path, "PNG")
                    temp_chart.Delete()
                    
                    excel.CutCopyMode = False
                except Exception as ex:
                    self.preview_label.configure(text=f"Не удалось экспортировать диапазон:\n{ex}")
                    return

            if os.path.exists(temp_path):
                self.preview_img = tkinter.PhotoImage(file=temp_path)
                w = self.preview_img.width()
                h = self.preview_img.height()
                
                factor = 1
                if w > 240 or h > 300:
                    factor = max(w // 240, h // 300) + 1
                    self.preview_img = self.preview_img.subsample(factor, factor)

                self.preview_label.configure(image=self.preview_img, text="")
            else:
                self.preview_label.configure(text="Файл изображения превью не сгенерирован")

        except Exception as e:
            self.preview_label.configure(text=f"Сбой при загрузке:\n{e}")

    def copy_selected_tag(self):
        selection = self.table_widget.selection()
        if not selection:
            return
        tag_name = self.table_widget.item(selection[0])["values"][0]
        self.copy_text_to_clipboard(tag_name)

    def copy_text_to_clipboard(self, text):
        if sys.platform == "win32":
            try:
                import win32clipboard
                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(win32clipboard.CF_UNICODETEXT, text)
                win32clipboard.CloseClipboard()
                self._show_clipboard_feedback()
                return
            except Exception as e:
                logger.warning(f"win32clipboard failed: {e}")

        try:
            self.clipboard_clear()
            self.clipboard_append(text)
            self.update()
            self._show_clipboard_feedback()
        except Exception as e:
            logger.error(f"Tkinter clipboard failed: {e}")
            messagebox.showerror("Ошибка", f"Не удалось скопировать в буфер:\n{e}", parent=self)

    def _show_clipboard_feedback(self):
        original_text = self.btn_copy_tag.cget("text")
        self.btn_copy_tag.configure(text="Скопировано!")
        self.after(1200, lambda: self.btn_copy_tag.configure(text=original_text))

    def browse_word_path(self):
        initial_dir = self.entry_def_dir.get().strip() or (os.path.dirname(self.config_path) if self.config_path else os.getcwd())
        file_path = filedialog.askopenfilename(
            title="Выберите файл шаблона Word",
            initialdir=initial_dir,
            filetypes=[("Файлы Word", "*.docx *.docm")],
            parent=self
        )
        if file_path:
            self.entry_word_path.delete(0, "end")
            self.entry_word_path.insert(0, os.path.normpath(file_path))

    def browse_def_dir(self):
        dir_path = filedialog.askdirectory(
            title="Выберите дефолтную папку Word",
            initialdir=os.getcwd(),
            parent=self
        )
        if dir_path:
            self.entry_def_dir.delete(0, "end")
            self.entry_def_dir.insert(0, os.path.normpath(dir_path))

    def browse_link_path(self):
        initial_dir = self.entry_def_dir.get().strip() or (os.path.dirname(self.config_path) if self.config_path else os.getcwd())
        file_path = filedialog.askopenfilename(
            title="Выберите Excel файл для привязки",
            initialdir=initial_dir,
            filetypes=[("Excel файлы", "*.xlsx *.xls *.xlsm")],
            parent=self
        )
        if file_path:
            norm_path = os.path.normpath(file_path)
            json_p = self.entry_json_path.get().strip()
            if json_p:
                try:
                    rel = os.path.relpath(norm_path, os.path.dirname(json_p))
                    if not rel.startswith(".."):
                        norm_path = rel
                except ValueError:
                    pass
            self.link_entry.delete(0, "end")
            self.link_entry.insert(0, norm_path)

    # --- Top Toolbar Actions ---
    def open_json_file(self):
        file_path = filedialog.askopenfilename(
            title="Открыть конфигурацию JSON",
            filetypes=[("Файлы JSON", "*.json")],
            parent=self
        )
        if file_path:
            try:
                loaded_cfg = config_loader.load_config_json(file_path)
                self.config = loaded_cfg
                self.config_path = os.path.normpath(file_path)
                self.load_config_data()
                
                self.controller.config = self.config
                self.controller.config_path = self.config_path
                self.controller.update_ui_from_config()
                
                logger.info(f"Loaded config inside ConfigBuilder: {self.config_path}")
            except Exception as e:
                messagebox.showerror("Ошибка загрузки", f"Не удалось загрузить файл:\n{e}", parent=self)

    def create_new_config(self):
        confirm = messagebox.askyesno("Новый проект", "Создать пустую конфигурацию? Несохраненные изменения будут утеряны.", parent=self)
        if confirm:
            self.config = ReportConfig()
            self.config_path = ""
            self.load_config_data()
            
            self.controller.config = self.config
            self.controller.config_path = ""
            self.controller.update_ui_from_config()
            
            logger.info("Created new blank configuration draft.")

    def close_config(self):
        confirm = messagebox.askyesno("Закрыть проект", "Выгрузить текущую конфигурацию из программы? Вы вернетесь к пустому состоянию.", parent=self)
        if confirm:
            self.config = ReportConfig()
            self.config_path = ""
            self.load_config_data()
            
            self.controller.config = self.config
            self.controller.config_path = ""
            self.controller.update_ui_from_config()
            
            logger.info("Configuration unloaded. MainWindow reset to default blank state.")
            self.destroy()

    def save_config_to_disk(self):
        json_path = self.entry_json_path.get().strip()
        if not json_path:
            initial_dir = self.entry_def_dir.get().strip() or os.getcwd()
            json_path = filedialog.asksaveasfilename(
                title="Сохранить JSON как...",
                initialdir=initial_dir,
                defaultextension=".json",
                filetypes=[("Файлы JSON", "*.json")],
                parent=self
            )
            if not json_path:
                return
                
        self.config.output_path = os.path.normpath(self.entry_word_path.get().strip())
        self.config.template_path = os.path.normpath(self.entry_word_path.get().strip())
        self.config.default_word_dir = os.path.normpath(self.entry_def_dir.get().strip())
        self.config.accent_color = self.opt_accent.get()

        try:
            config_loader.save_config_json(self.config, json_path)
            self.config_path = os.path.normpath(json_path)
            self.entry_json_path.delete(0, "end")
            self.entry_json_path.insert(0, self.config_path)
            
            self.controller.config = self.config
            self.controller.config_path = self.config_path
            self.controller.update_ui_from_config()
            
            messagebox.showinfo("Сохранено", f"Конфигурация успешно сохранена:\n{self.config_path}", parent=self)
        except Exception as e:
            messagebox.showerror("Ошибка сохранения", f"Не удалось сохранить конфигурацию:\n{e}", parent=self)
