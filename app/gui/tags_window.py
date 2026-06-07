import os
import logging
import tkinter
from tkinter import messagebox
import customtkinter
from app.models.config import ReportConfig, TopicItem
from app.services import config_loader

logger = logging.getLogger("DocBuilder.TagsWindow")

class TagsWindow(customtkinter.CTkFrame):
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
        
        if hasattr(self, "btn_back"):
            self.btn_back.configure(
                fg_color=colors["surface2"],
                hover_color=colors["border"],
                text_color=colors["text"]
            )
            
        if hasattr(self, "list_label"):
            self.list_label.configure(text_color=colors["textSecondary"])
            
        if hasattr(self, "editor_lbl"):
            self.editor_lbl.configure(text_color=colors["textSecondary"])
            
        self.save_btn.configure(
            fg_color=colors["primary"],
            hover_color=colors["primaryHover"],
            text_color="#ffffff"
        )
        self.text_editor.configure(
            fg_color=colors["surface"],
            border_color=colors["border"],
            text_color=colors["text"]
        )
        self.tags_list.configure(
            bg=colors["surface"],
            fg=colors["text"],
            selectbackground=colors["primarySoft"],
            selectforeground=colors["primary"],
            highlightbackground=colors["border"],
            highlightcolor=colors["primary"]
        )
        self.details_label.configure(text_color=colors["textSecondary"])
        self.info_area.configure(text_color=colors["textSecondary"])

    def init_ui(self):
        # Configure layout (row 0 is header, row 1 is contents)
        self.grid_columnconfigure(0, weight=35, minsize=250)
        self.grid_columnconfigure(1, weight=65, minsize=450)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)

        accent = self.get_accent_theme()

        # 0. Navigation Header Bar (Row 0)
        header_bar = customtkinter.CTkFrame(self, fg_color="transparent")
        header_bar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=(4, 0))
        
        self.btn_back = customtkinter.CTkButton(
            header_bar, text="← Назад в меню", width=120, height=28, 
            font=("Segoe UI", 11, "bold"), fg_color="#333333", hover_color="#444444",
            command=self.go_back
        )
        self.btn_back.pack(side="left", padx=(0, 12))

        self.lbl_title = customtkinter.CTkLabel(
            header_bar, text="СПИСОК ТЕГОВ И СТАТЕЙ", font=("Segoe UI", 14, "bold"),
            text_color=accent["fg"]
        )
        self.lbl_title.pack(side="left")

        # 1. Left Panel (List of Tags) (Row 1, Column 0)
        self.left_panel = customtkinter.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.left_panel.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self.left_panel.grid_columnconfigure(0, weight=1)
        self.left_panel.grid_rowconfigure(1, weight=1)

        self.list_label = customtkinter.CTkLabel(
            self.left_panel, 
            text="Список всех тегов:", 
            font=("Segoe UI", 11, "bold"),
            text_color="#CCCCCC"
        )
        self.list_label.grid(row=0, column=0, sticky="w", pady=(0, 5))

        list_container = customtkinter.CTkFrame(self.left_panel, fg_color="transparent")
        list_container.grid(row=1, column=0, sticky="nsew")
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

        # 2. Right Panel (Details / Editor) (Row 1, Column 1)
        self.right_panel = customtkinter.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.right_panel.grid(row=1, column=1, sticky="nsew", padx=10, pady=10)
        self.right_panel.grid_columnconfigure(0, weight=1)
        self.right_panel.grid_rowconfigure(1, weight=1)

        self.details_label = customtkinter.CTkLabel(
            self.right_panel, 
            text="Свойства тега", 
            font=("Segoe UI", 13, "bold"),
            text_color="#CCCCCC"
        )
        self.details_label.grid(row=0, column=0, sticky="w", pady=(0, 10))

        # Default info
        self.info_area = customtkinter.CTkLabel(
            self.right_panel,
            text="Выберите тег из списка слева для просмотра свойств или редактирования текста.",
            font=("Segoe UI", 11, "italic"),
            text_color="#888888",
            wraplength=420,
            justify="left",
            anchor="nw"
        )
        self.info_area.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)

        # Editor container (shown for TOPIC tags)
        self.editor_container = customtkinter.CTkFrame(self.right_panel, fg_color="transparent")
        self.editor_container.grid_columnconfigure(0, weight=1)
        self.editor_container.grid_rowconfigure(1, weight=1)

        self.editor_lbl = customtkinter.CTkLabel(self.editor_container, text="Текст топика:", font=("Segoe UI", 11))
        self.editor_lbl.grid(row=0, column=0, sticky="w", pady=(0, 5))

        self.text_editor = customtkinter.CTkTextbox(
            self.editor_container,
            fg_color="#18181b",
            text_color="#ffffff",
            border_width=1,
            border_color="#27272a",
            corner_radius=6,
            font=("Segoe UI", 11)
        )
        self.text_editor.grid(row=1, column=0, sticky="nsew", pady=(0, 10))

        self.save_btn = customtkinter.CTkButton(
            self.editor_container,
            text="Сохранить текст",
            font=("Segoe UI", 11, "bold"),
            fg_color=accent["fg"],
            hover_color=accent["hover"],
            command=self.save_topic_text
        )
        self.save_btn.grid(row=2, column=0, sticky="ew")

    def go_back(self):
        # Save if text editor has topic
        if self.editor_container.winfo_ismapped():
            self.save_topic_text()
        if hasattr(self.controller, "show_dashboard"):
            self.controller.show_dashboard()

    def load_config_data(self):
        self.refresh_theme_colors()
        self.tags_list.delete(0, "end")
        for tag in self.config.tags:
            self.tags_list.insert("end", tag)

    def tag_selection_changed(self, event=None):
        selection = self.tags_list.curselection()
        if not selection:
            self.info_area.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
            self.editor_container.grid_forget()
            self.details_label.configure(text="Свойства тега")
            return

        tag_name = self.tags_list.get(selection[0])
        self.details_label.configure(text=f"Свойства тега: {tag_name}")
        
        is_topic = tag_name.startswith("<TOPIC")
        is_table = tag_name.startswith("<TableTag_")
        is_chart = tag_name.startswith("<ChartTag_")

        if is_topic:
            self.info_area.grid_forget()
            self.editor_container.grid(row=1, column=0, sticky="nsew")
            
            topic_item = next((x for x in self.config.topics if x.tag == tag_name), None)
            self.text_editor.delete("1.0", "end")
            if topic_item and topic_item.text:
                self.text_editor.insert("1.0", topic_item.text)
        else:
            self.editor_container.grid_forget()
            self.info_area.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
            
            if is_table:
                table_item = next((x for x in self.config.tables if x.tag == tag_name), None)
                if table_item:
                    rng = f"{table_item.range_a}:{table_item.range_b}" if table_item.range_b else table_item.range_a
                    info = (
                        f"Тип: Диапазон Excel\n\n"
                        f"Ссылка: {table_item.excel_path}\n"
                        f"Лист: {table_item.sheet}\n"
                        f"Диапазон: {rng}\n"
                        f"Использование: {'Да' if table_item.use else 'Нет'}\n"
                        f"Заголовок: {'Да' if table_item.header else 'Нет'}"
                    )
                else:
                    info = "Тип: Диапазон Excel (Нет привязки в конфигурации)"
            elif is_chart:
                chart_item = next((x for x in self.config.charts if x.tag == tag_name), None)
                if chart_item:
                    info = (
                        f"Тип: Диаграмма Excel\n\n"
                        f"Ссылка: {chart_item.excel_path}\n"
                        f"Лист: {chart_item.sheet}\n"
                        f"Номер графика: {chart_item.chart_id}"
                    )
                else:
                    info = "Тип: Диаграмма Excel (Нет привязки в конфигурации)"
            else:
                info = f"Тип: Пользовательский тег (Вне каталога)"
                
            self.info_area.configure(text=info)

    def save_topic_text(self):
        selection = self.tags_list.curselection()
        if not selection:
            return

        tag_name = self.tags_list.get(selection[0])
        text = self.text_editor.get("1.0", "end").strip()
        
        topic_item = next((x for x in self.config.topics if x.tag == tag_name), None)
        if topic_item:
            topic_item.text = text
        else:
            self.config.topics.append(TopicItem(tag=tag_name, text=text))
            
        if self.config_path:
            try:
                config_loader.save_config_json(self.config, self.config_path)
                logger.info(f"Saved topic text for {tag_name} to disk.")
                self.emit_config_updated()
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось сохранить на диск:\n{e}", parent=self)
        else:
            messagebox.showwarning("Предупреждение", "Конфигурационный файл не загружен.", parent=self)
