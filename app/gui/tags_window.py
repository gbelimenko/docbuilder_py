import os
import logging
import tkinter
from tkinter import messagebox
import customtkinter
from app.models.config import ReportConfig, TopicItem
from app.services import config_loader

logger = logging.getLogger("DocBuilder.TagsWindow")

class TagsWindow(customtkinter.CTkToplevel):
    def __init__(self, config: ReportConfig, config_path: str, parent=None):
        super().__init__(parent)
        self.config = config
        self.config_path = config_path
        
        self.title("DocBuilder | Список тегов и статей")
        self.geometry("800x500")
        
        # Make modal
        self.transient(parent)
        self.grab_set()
        
        self._config_updated_callbacks = []
        self.init_ui()
        self.load_config_data()
        
        # Center the window relative to parent
        if parent:
            self.geometry(f"+{parent.winfo_x() + 50}+{parent.winfo_y() + 50}")

    def config_updated_connect(self, callback):
        self._config_updated_callbacks.append(callback)

    def emit_config_updated(self):
        for cb in self._config_updated_callbacks:
            cb()

    def init_ui(self):
        # Configure layout (2 columns: left for tag list, right for editor/details)
        self.grid_columnconfigure(0, weight=35, minsize=250)
        self.grid_columnconfigure(1, weight=65, minsize=450)
        self.grid_rowconfigure(0, weight=1)

        # Left Panel (List of Tags)
        self.left_panel = customtkinter.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.left_panel.grid_columnconfigure(0, weight=1)
        self.left_panel.grid_rowconfigure(1, weight=1)

        list_label = customtkinter.CTkLabel(
            self.left_panel, 
            text="Список всех тегов:", 
            font=("Segoe UI", 11, "bold"),
            text_color="#CCCCCC"
        )
        list_label.grid(row=0, column=0, sticky="w", pady=(0, 5))

        # We use a frame to hold Listbox + scrollbar
        list_container = customtkinter.CTkFrame(self.left_panel, fg_color="transparent")
        list_container.grid(row=1, column=0, sticky="nsew")
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
        self.tags_list.bind('<<ListboxSelect>>', self.tag_selection_changed)

        scrollbar = customtkinter.CTkScrollbar(list_container, orientation="vertical", command=self.tags_list.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tags_list.config(yscrollcommand=scrollbar.set)

        # Right Panel (Details / Editor)
        self.right_panel = customtkinter.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.right_panel.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.right_panel.grid_columnconfigure(0, weight=1)
        self.right_panel.grid_rowconfigure(1, weight=1)

        self.details_label = customtkinter.CTkLabel(
            self.right_panel, 
            text="Свойства тега", 
            font=("Segoe UI", 13, "bold"),
            text_color="#CCCCCC"
        )
        self.details_label.grid(row=0, column=0, sticky="w", pady=(0, 10))

        # Default info label (shown when no tag selected or non-topic tag selected)
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
        # Gridded on row 1, column 0, but hidden by default
        self.editor_container.grid_columnconfigure(0, weight=1)
        self.editor_container.grid_rowconfigure(1, weight=1)

        editor_lbl = customtkinter.CTkLabel(self.editor_container, text="Текст топика:", font=("Segoe UI", 11))
        editor_lbl.grid(row=0, column=0, sticky="w", pady=(0, 5))

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
            command=self.save_topic_text
        )
        self.save_btn.grid(row=2, column=0, sticky="ew")

    def load_config_data(self):
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
        
        # Find item or create it
        topic_item = next((x for x in self.config.topics if x.tag == tag_name), None)
        if topic_item:
            topic_item.text = text
        else:
            self.config.topics.append(TopicItem(tag=tag_name, text=text))
            
        # Save to disk
        if self.config_path:
            try:
                config_loader.save_config_json(self.config, self.config_path)
                logger.info(f"Saved topic text for {tag_name} to disk.")
                self.emit_config_updated()
                messagebox.showinfo("Сохранено", f"Текст для статьи {tag_name} успешно сохранен!", parent=self)
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось сохранить на диск:\n{e}", parent=self)
        else:
            messagebox.showwarning("Предупреждение", "Конфигурационный файл не загружен.", parent=self)
