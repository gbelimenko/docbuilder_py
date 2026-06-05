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

class ConfigBuilderFrame(customtkinter.CTkFrame):
    def __init__(self, parent, controller, config: ReportConfig = None, config_path: str = ""):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        
        # Keep track of local config copy for draft editing
        self.config_path = config_path
        if config:
            # Create a shallow/deep copy using pydantic model_validate
            self.config = ReportConfig(**config.model_dump())
        else:
            self.config = ReportConfig()
            
        self._config_updated_callbacks = []
        self.preview_img = None
        
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
        self.lbl_title.configure(text_color=accent["fg"])
        self.btn_save_config.configure(fg_color=accent["fg"], hover_color=accent["hover"])
        self.btn_grab.configure(fg_color=accent["fg"], hover_color=accent["hover"])
        self.btn_copy_tag.configure(fg_color=accent["fg"], hover_color=accent["hover"])
        self.tags_list.configure(selectforeground=accent["fg"])

    def init_ui(self):
        # 3-column layout: Left (listbox), Middle (editors), Right (preview)
        self.grid_columnconfigure(0, weight=25, minsize=240)
        self.grid_columnconfigure(1, weight=50, minsize=420)
        self.grid_columnconfigure(2, weight=25, minsize=260)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)

        accent = self.get_accent_theme()

        # 0. Navigation Header Bar (Row 0)
        header_bar = customtkinter.CTkFrame(self, fg_color="transparent")
        header_bar.grid(row=0, column=0, columnspan=3, sticky="ew", padx=12, pady=(4, 0))
        
        btn_back = customtkinter.CTkButton(
            header_bar, text="← Назад в меню", width=120, height=28, 
            font=("Segoe UI", 11, "bold"), fg_color="#333333", hover_color="#444444",
            command=self.go_back
        )
        btn_back.pack(side="left", padx=(0, 12))

        self.lbl_title = customtkinter.CTkLabel(
            header_bar, text="КОНСТРУКТОР КОНФИГУРАЦИИ (JSON)", font=("Segoe UI", 14, "bold"),
            text_color=accent["fg"]
        )
        self.lbl_title.pack(side="left")

        # 1. Left Panel: Tag Listbox & Controls
        left_panel = customtkinter.CTkFrame(self, fg_color="transparent")
        left_panel.grid(row=1, column=0, sticky="nsew", padx=12, pady=12)
        left_panel.grid_columnconfigure(0, weight=1)
        left_panel.grid_rowconfigure(1, weight=1)

        lbl_tags = customtkinter.CTkLabel(left_panel, text="Список тегов:", font=("Segoe UI", 11, "bold"), text_color="#aaaaaa")
        lbl_tags.grid(row=0, column=0, sticky="w", pady=(0, 4))

        list_container = customtkinter.CTkFrame(left_panel, fg_color="transparent")
        list_container.grid(row=1, column=0, sticky="nsew", pady=(0, 8))
        list_container.grid_columnconfigure(0, weight=1)
        list_container.grid_rowconfigure(0, weight=1)

        self.tags_list = tkinter.Listbox(
            list_container,
            bg="#0c0c0e",
            fg="#e4e4e7",
            selectbackground="#27272a",
            selectforeground=accent["fg"],
            bd=1,
            highlightthickness=1,
            highlightbackground="#1f1f24",
            highlightcolor=accent["fg"],
            font=("Segoe UI", 11),
            relief="flat"
        )
        self.tags_list.grid(row=0, column=0, sticky="nsew")
        self.tags_list.bind('<<ListboxSelect>>', self.tag_selection_changed)

        scrollbar = customtkinter.CTkScrollbar(list_container, orientation="vertical", command=self.tags_list.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tags_list.config(yscrollcommand=scrollbar.set)

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
        lbl_cfg_section = customtkinter.CTkLabel(self.middle_panel, text="Настройки конфигурации (JSON):", font=("Segoe UI", 12, "bold"), text_color="#3b82f6")
        lbl_cfg_section.grid(row=0, column=0, sticky="w", padx=10, pady=(8, 4))

        cfg_box = customtkinter.CTkFrame(self.middle_panel, fg_color="#1c1c1f", border_width=1, border_color="#2d2d30")
        cfg_box.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 12))
        cfg_box.grid_columnconfigure(1, weight=1)

        # JSON Path
        customtkinter.CTkLabel(cfg_box, text="Файл JSON:").grid(row=0, column=0, padx=8, pady=4, sticky="e")
        self.entry_json_path = customtkinter.CTkEntry(cfg_box, font=("Segoe UI", 11))
        self.entry_json_path.grid(row=0, column=1, sticky="ew", padx=4, pady=4)
        btn_json_browse = customtkinter.CTkButton(cfg_box, text="...", width=32, height=28, command=self.browse_json_path)
        btn_json_browse.grid(row=0, column=2, padx=8, pady=4)

        # Word Template Path
        customtkinter.CTkLabel(cfg_box, text="Файл Word:").grid(row=1, column=0, padx=8, pady=4, sticky="e")
        self.entry_word_path = customtkinter.CTkEntry(cfg_box, font=("Segoe UI", 11))
        self.entry_word_path.grid(row=1, column=1, sticky="ew", padx=4, pady=4)
        btn_word_browse = customtkinter.CTkButton(cfg_box, text="...", width=32, height=28, command=self.browse_word_path)
        btn_word_browse.grid(row=1, column=2, padx=8, pady=4)

        # Default Word Folder
        customtkinter.CTkLabel(cfg_box, text="Дефолт. папка:").grid(row=2, column=0, padx=8, pady=4, sticky="e")
        self.entry_def_dir = customtkinter.CTkEntry(cfg_box, font=("Segoe UI", 11))
        self.entry_def_dir.grid(row=2, column=1, sticky="ew", padx=4, pady=4)
        btn_dir_browse = customtkinter.CTkButton(cfg_box, text="...", width=32, height=28, command=self.browse_def_dir)
        btn_dir_browse.grid(row=2, column=2, padx=8, pady=4)

        # Accent Theme
        customtkinter.CTkLabel(cfg_box, text="Цвет темы:").grid(row=3, column=0, padx=8, pady=4, sticky="e")
        self.opt_accent = customtkinter.CTkOptionMenu(cfg_box, values=["blue", "emerald", "rose", "amber", "purple"], command=self.change_accent_from_ui)
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
            self.middle_panel, text="СОХРАНИТЬ КОНФИГУРАЦИЮ (JSON)", height=38,
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

        preview_container = customtkinter.CTkFrame(right_panel, fg_color="#0d0d0f", border_width=1, border_color="#27272a")
        preview_container.grid(row=1, column=0, sticky="nsew", pady=(0, 8))
        preview_container.grid_columnconfigure(0, weight=1)
        preview_container.grid_rowconfigure(0, weight=1)

        # Label inside frame to display images
        self.preview_label = customtkinter.CTkLabel(
            preview_container, text="Выберите тег табличного\nдиапазона или графика\nдля вывода картинки.",
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
        self.entry_json_path.insert(0, self.config_path)

        self.entry_word_path.delete(0, "end")
        self.entry_word_path.insert(0, self.config.output_path)

        self.entry_def_dir.delete(0, "end")
        self.entry_def_dir.insert(0, self.config.default_word_dir)

        # Set accent opt dropdown
        accent_val = getattr(self.config, "accent_color", "blue") or "blue"
        if accent_val in ["blue", "emerald", "rose", "amber", "purple"]:
            self.opt_accent.set(accent_val)
        else:
            self.opt_accent.set("blue")

        # Load listbox
        self.tags_list.delete(0, "end")
        for tag in self.config.tags:
            self.tags_list.insert("end", tag)

        # Clear editor and previews
        self.lbl_no_tag.pack(padx=20, pady=40)
        self.editor_fields.grid_forget()
        self.preview_label.configure(image="", text="Выберите тег табличного\nдиапазона или графика\nдля вывода картинки.")

    def change_accent_from_ui(self, val):
        self.config.accent_color = val
        self.refresh_theme_colors()
        # Notify controller if needed
        if hasattr(self.controller, "config"):
            self.controller.config.accent_color = val
            if hasattr(self.controller, "apply_theme"):
                self.controller.apply_theme()

    def go_back(self):
        # Check if unsaved
        confirm = messagebox.askyesno(
            "Подтверждение", 
            "Вы уверены, что хотите выйти из конструктора?\nНесохраненные изменения конфигурации будут утеряны.",
            parent=self
        )
        if confirm:
            if hasattr(self.controller, "show_dashboard"):
                self.controller.show_dashboard()

    def tag_selection_changed(self, event=None):
        selection = self.tags_list.curselection()
        if not selection:
            self.lbl_no_tag.pack(padx=20, pady=40)
            self.editor_fields.grid_forget()
            return

        # Hide placeholder
        self.lbl_no_tag.pack_forget()
        self.editor_fields.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)

        tag_name = self.tags_list.get(selection[0])
        self.lbl_editor_section.configure(text=f"Свойства тега: {tag_name}")

        # Auto clear preview on selection to avoid displaying outdated data
        self.preview_label.configure(image="", text="Нажмите кнопку ниже,\nчтобы загрузить изображение.")

        # Show appropriate widgets based on type
        is_table = tag_name.startswith("<TableTag_")
        is_chart = tag_name.startswith("<ChartTag_")
        is_topic = tag_name.startswith("<TOPIC")

        self.tag_entry.delete(0, "end")
        self.tag_entry.insert(0, tag_name)

        if is_table:
            # Show table inputs
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
            
            # Hide chart & topic
            self.lbl_chart_id.grid_remove()
            self.chart_id_entry.grid_remove()
            self.lbl_topic_text.grid_remove()
            self.topic_textbox.grid_remove()

            # Load values
            item = next((x for x in self.config.tables if x.tag == tag_name), None)
            if item:
                self.link_entry.delete(0, "end")
                self.link_entry.insert(0, item.excel_path)
                self.sheet_entry.delete(0, "end")
                self.sheet_entry.insert(0, item.sheet)
                self.range_a_entry.delete(0, "end")
                self.range_a_entry.insert(0, item.range_a)
                self.range_b_entry.delete(0, "end")
                self.range_b_entry.insert(0, item.range_b)
                self.use_var.set(item.use)
                self.hdr_var.set(item.header)
            else:
                self.link_entry.delete(0, "end")
                self.sheet_entry.delete(0, "end")
                self.range_a_entry.delete(0, "end")
                self.range_b_entry.delete(0, "end")
                self.use_var.set(True)
                self.hdr_var.set(False)

        elif is_chart:
            # Show chart inputs
            self.lbl_link.grid()
            self.link_frame.grid()
            self.lbl_sheet.grid()
            self.sheet_entry.grid()
            self.lbl_chart_id.grid()
            self.chart_id_entry.grid()
            
            # Hide table & topic
            self.lbl_range_a.grid_remove()
            self.range_a_entry.grid_remove()
            self.lbl_range_b.grid_remove()
            self.range_b_entry.grid_remove()
            self.chk_use.grid_remove()
            self.chk_hdr.grid_remove()
            self.lbl_topic_text.grid_remove()
            self.topic_textbox.grid_remove()

            # Load values
            item = next((x for x in self.config.charts if x.tag == tag_name), None)
            if item:
                self.link_entry.delete(0, "end")
                self.link_entry.insert(0, item.excel_path)
                self.sheet_entry.delete(0, "end")
                self.sheet_entry.insert(0, item.sheet)
                self.chart_id_entry.delete(0, "end")
                self.chart_id_entry.insert(0, str(item.chart_id))
            else:
                self.link_entry.delete(0, "end")
                self.sheet_entry.delete(0, "end")
                self.chart_id_entry.delete(0, "end")
                self.chart_id_entry.insert(0, "1")

        elif is_topic:
            # Show topic inputs
            self.lbl_topic_text.grid()
            self.topic_textbox.grid()

            # Hide others
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

            # Load text
            item = next((x for x in self.config.topics if x.tag == tag_name), None)
            self.topic_textbox.delete("1.0", "end")
            if item and item.text:
                self.topic_textbox.insert("1.0", item.text)

        else:
            # Custom tag, hide everything else
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
        selection = self.tags_list.curselection()
        if not selection:
            return

        old_tag = self.tags_list.get(selection[0])
        new_tag = self.tag_entry.get().strip()

        if not new_tag:
            messagebox.showwarning("Ошибка", "Имя тега не может быть пустым.", parent=self)
            return

        is_table = old_tag.startswith("<TableTag_")
        is_chart = old_tag.startswith("<ChartTag_")
        is_topic = old_tag.startswith("<TOPIC")

        # 1. Update tag name in main tags array
        tags_idx = self.config.tags.index(old_tag)
        self.config.tags[tags_idx] = new_tag

        # 2. Update specific lists
        if is_table:
            item = next((x for x in self.config.tables if x.tag == old_tag), None)
            if item:
                item.tag = new_tag
                item.excel_path = self.link_entry.get().strip()
                item.sheet = self.sheet_entry.get().strip()
                item.range_a = self.range_a_entry.get().strip()
                item.range_b = self.range_b_entry.get().strip()
                item.use = self.use_var.get()
                item.header = self.hdr_var.get()
        elif is_chart:
            item = next((x for x in self.config.charts if x.tag == old_tag), None)
            if item:
                item.tag = new_tag
                item.excel_path = self.link_entry.get().strip()
                item.sheet = self.sheet_entry.get().strip()
                try:
                    item.chart_id = int(self.chart_id_entry.get().strip())
                except ValueError:
                    item.chart_id = 1
        elif is_topic:
            item = next((x for x in self.config.topics if x.tag == old_tag), None)
            text_val = self.topic_textbox.get("1.0", "end").strip()
            if item:
                item.tag = new_tag
                item.text = text_val
            else:
                self.config.topics.append(TopicItem(tag=new_tag, text=text_val))

        # Refresh listbox and reselect updated row
        self.tags_list.delete(0, "end")
        for tag in self.config.tags:
            self.tags_list.insert("end", tag)
            
        new_sel_idx = self.config.tags.index(new_tag)
        self.tags_list.selection_set(new_sel_idx)
        self.tags_list.see(new_sel_idx)
        self.tag_selection_changed()

        logger.info(f"Tag changes applied: {old_tag} -> {new_tag}")

    def add_tag_manual(self):
        # Ask for new tag type
        tag_type = messagebox.askquestion("Выбор типа", "Создать таблицу? (Если 'Нет' - создастся график)", parent=self)
        if tag_type == "yes":
            # Table tag
            max_num = 0
            for tag in self.config.tags:
                if tag.startswith("<TableTag_"):
                    num = re.search(r'\d+', tag)
                    if num: max_num = max(max_num, int(num.group(0)))
            new_tag = f"<TableTag_{max_num + 1}>"
            self.config.tables.append(TableItem(tag=new_tag, excel_path="", sheet="Sheet1", range_a="A1", range_b="", use=True, header=False))
        else:
            # Chart tag
            max_num = 0
            for tag in self.config.tags:
                if tag.startswith("<ChartTag_"):
                    num = re.search(r'\d+', tag)
                    if num: max_num = max(max_num, int(num.group(0)))
            new_tag = f"<ChartTag_{max_num + 1}>"
            self.config.charts.append(ChartItem(tag=new_tag, excel_path="", sheet="Sheet1", chart_id=1))

        self.config.tags.append(new_tag)
        self.tags_list.insert("end", new_tag)
        
        idx = self.tags_list.size() - 1
        self.tags_list.selection_clear(0, "end")
        self.tags_list.selection_set(idx)
        self.tags_list.see(idx)
        self.tag_selection_changed()

    def delete_selected_tag(self):
        selection = self.tags_list.curselection()
        if not selection:
            return

        tag_name = self.tags_list.get(selection[0])
        confirm = messagebox.askyesno("Удаление", f"Удалить тег {tag_name} из конфигурации?", parent=self)
        if confirm:
            if tag_name in self.config.tags:
                self.config.tags.remove(tag_name)
                
            # Remove from type list
            if tag_name.startswith("<TableTag_"):
                self.config.tables = [x for x in self.config.tables if x.tag != tag_name]
            elif tag_name.startswith("<ChartTag_"):
                self.config.charts = [x for x in self.config.charts if x.tag != tag_name]
            elif tag_name.startswith("<TOPIC"):
                self.config.topics = [x for x in self.config.topics if x.tag != tag_name]

            self.load_config_data()

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
            
            # Case 1: Active Chart selected in Excel
            if active_chart is not None:
                chart_shape = active_chart.Parent
                ws = chart_shape.Parent
                wb = ws.Parent

                excel_path = wb.FullName
                sheet_name = ws.Name
                chart_name = chart_shape.Name
                
                num_match = re.search(r'\d+', chart_name)
                chart_id = int(num_match.group(0)) if num_match else 1

                # Make relative to JSON if path exists
                if self.config_path:
                    try:
                        rel = os.path.relpath(excel_path, os.path.dirname(self.config_path))
                        if not rel.startswith(".."):
                            excel_path = rel
                    except ValueError:
                        pass

                # Find unique ChartTag ID
                max_num = 0
                for tag in self.config.tags:
                    if tag.startswith("<ChartTag_"):
                        num = re.search(r'\d+', tag)
                        if num: max_num = max(max_num, int(num.group(0)))
                new_tag = f"<ChartTag_{max_num + 1}>"

                # Save model
                self.config.charts.append(ChartItem(
                    tag=new_tag,
                    excel_path=excel_path,
                    sheet=sheet_name,
                    chart_id=chart_id
                ))
                self.config.tags.append(new_tag)
                self.tags_list.insert("end", new_tag)

                # Select new item
                new_idx = self.tags_list.size() - 1
                self.tags_list.selection_clear(0, "end")
                self.tags_list.selection_set(new_idx)
                self.tags_list.see(new_idx)
                self.tag_selection_changed()

                # Robust clipboard copy
                self.copy_text_to_clipboard(new_tag)

                # Instantly load preview
                self.load_preview()

                messagebox.showinfo(
                    "Успешный захват графика",
                    f"Добавлен график № {chart_id} на листе '{sheet_name}'.\n\n"
                    f"Создан новый тег: {new_tag} (скопирован в буфер обмена!).",
                    parent=self
                )
                return

            # Case 2: Range selected
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
            address = sel.Address(RowAbsolute=False, ColumnAbsolute=False)

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

            # Unique TableTag
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
            self.tags_list.insert("end", new_tag)

            # Select and load preview
            new_idx = self.tags_list.size() - 1
            self.tags_list.selection_clear(0, "end")
            self.tags_list.selection_set(new_idx)
            self.tags_list.see(new_idx)
            self.tag_selection_changed()

            # Copy tag
            self.copy_text_to_clipboard(new_tag)

            # Instantly load preview
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
        selection = self.tags_list.curselection()
        if not selection:
            return

        tag_name = self.tags_list.get(selection[0])
        self.preview_label.configure(image="", text="Загрузка превью из Excel...")
        self.update()

        if sys.platform != "win32":
            self.preview_label.configure(text="Предпросмотр доступен только на Windows")
            return

        try:
            import win32com.client
            is_table = tag_name.startswith("<TableTag_")
            is_chart = tag_name.startswith("<ChartTag_")

            if is_table:
                item = next((x for x in self.config.tables if x.tag == tag_name), None)
            elif is_chart:
                item = next((x for x in self.config.charts if x.tag == tag_name), None)
            else:
                self.preview_label.configure(text="Предпросмотр для топиков не поддерживается")
                return

            if not item or not item.excel_path:
                self.preview_label.configure(text="Путь к Excel не заполнен")
                return

            resolved_path = resolve_dynamic_path(item.excel_path, self.config_path)
            if not os.path.exists(resolved_path):
                self.preview_label.configure(text=f"Файл Excel не найден:\n{item.excel_path}")
                return

            # Connect to Excel
            try:
                excel = win32com.client.GetActiveObject("Excel.Application")
            except Exception:
                self.preview_label.configure(text="Excel не запущен")
                return

            # Check open workbooks
            wb = None
            for open_wb in excel.Workbooks:
                if os.path.normpath(open_wb.FullName).lower() == os.path.normpath(resolved_path).lower():
                    wb = open_wb
                    break

            if wb is None:
                wb = excel.Workbooks.Open(resolved_path, ReadOnly=True)

            try:
                ws = wb.Worksheets(item.sheet)
            except Exception:
                self.preview_label.configure(text=f"Лист '{item.sheet}' не найден в файле")
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
                    # Retrieve chart shape
                    try:
                        chart_obj = ws.ChartObjects(int(item.chart_id))
                    except Exception:
                        chart_obj = ws.ChartObjects(item.chart_id)
                    chart_obj.Chart.Export(temp_path, "PNG")
                except Exception as ex:
                    self.preview_label.configure(text=f"Не удалось экспортировать график:\n{ex}")
                    return
            else:
                # Table range
                try:
                    addr = item.range_a
                    if item.range_b:
                        addr += f":{item.range_b}"
                    rng = ws.Range(addr)
                    
                    rng.Copy()
                    
                    # Create temporary chart as proxy to export image
                    temp_chart = ws.ChartObjects().Add(0, 0, rng.Width, rng.Height)
                    temp_chart.Chart.Paste()
                    temp_chart.Chart.Export(temp_path, "PNG")
                    temp_chart.Delete()
                    
                    excel.CutCopyMode = False
                except Exception as ex:
                    self.preview_label.configure(text=f"Не удалось экспортировать диапазон:\n{ex}")
                    return

            # Display image in Tkinter PhotoImage
            if os.path.exists(temp_path):
                self.preview_img = tkinter.PhotoImage(file=temp_path)
                w = self.preview_img.width()
                h = self.preview_img.height()
                
                # Shrink if too big
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
        selection = self.tags_list.curselection()
        if not selection:
            return
        tag_name = self.tags_list.get(selection[0])
        self.copy_text_to_clipboard(tag_name)

    def copy_text_to_clipboard(self, text):
        if sys.platform == "win32":
            try:
                import win32clipboard
                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardText(text)
                win32clipboard.CloseClipboard()
                self._show_clipboard_feedback()
                return
            except Exception as e:
                logger.warning(f"win32clipboard failed: {e}")

        # Fallback to standard Tkinter Clipboard
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

    # --- Path Helpers ---
    def browse_json_path(self):
        initial_dir = self.entry_def_dir.get().strip() or (os.path.dirname(self.config_path) if self.config_path else os.getcwd())
        file_path = filedialog.asksaveasfilename(
            title="Выберите куда сохранить JSON файл",
            initialdir=initial_dir,
            defaultextension=".json",
            filetypes=[("Файлы JSON", "*.json")],
            parent=self
        )
        if file_path:
            self.entry_json_path.delete(0, "end")
            self.entry_json_path.insert(0, os.path.normpath(file_path))

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

    # --- Save to Disk ---
    def save_config_to_disk(self):
        json_path = self.entry_json_path.get().strip()
        if not json_path:
            messagebox.showwarning("Ошибка", "Пожалуйста, укажите путь для сохранения JSON-файла.", parent=self)
            return

        self.config.output_path = os.path.normpath(self.entry_word_path.get().strip())
        self.config.template_path = os.path.normpath(self.entry_word_path.get().strip())
        self.config.default_word_dir = os.path.normpath(self.entry_def_dir.get().strip())
        self.config.accent_color = self.opt_accent.get()

        try:
            config_loader.save_config_json(self.config, json_path)
            self.config_path = os.path.normpath(json_path)
            
            # Feed back changes to controller
            if hasattr(self.controller, "config"):
                self.controller.config = self.config
                self.controller.config_path = self.config_path
                self.controller.update_ui_from_config()
                
            self.emit_config_updated()
            messagebox.showinfo("Сохранено", f"Конфигурация успешно сохранена на диск:\n{self.config_path}", parent=self)
            
            # Automatically navigate to menu
            if hasattr(self.controller, "show_dashboard"):
                self.controller.show_dashboard()
        except Exception as e:
            messagebox.showerror("Ошибка сохранения", f"Не удалось сохранить конфигурацию:\n{e}", parent=self)
