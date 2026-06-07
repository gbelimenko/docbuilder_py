import customtkinter
import queue
from app.utils.logging_config import queue_log_handler

class LogViewer(customtkinter.CTkFrame):
    """
    A custom log viewer widget that styles log messages based on level
    and appends them to a dark-themed text area with a clean developer terminal design.
    Uses CustomTkinter and thread-safe queue polling.
    """
    def __init__(self, parent=None, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.init_ui()
        self.check_queue()

    def init_ui(self):
        # Configure grid layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header panel
        self.header = customtkinter.CTkFrame(self, fg_color="transparent")
        self.header.grid(row=0, column=0, sticky="ew", pady=(0, 6))

        self.title = customtkinter.CTkLabel(
            self.header, 
            text="System Log / Лог работы",
            font=("Segoe UI", 11, "bold"),
            text_color="#888892"
        )
        self.title.pack(side="left", anchor="w")

        self.clear_btn = customtkinter.CTkButton(
            self.header,
            text="Очистить",
            width=70,
            height=24,
            fg_color="#1e1e24",
            hover_color="#2b2b35",
            text_color="#a1a1aa",
            font=("Segoe UI", 10, "bold"),
            command=self.clear_logs
        )
        self.clear_btn.pack(side="right", anchor="e")

        # Text Console
        self.console = customtkinter.CTkTextbox(
            self,
            font=("Consolas", 11),
            fg_color="#0b0b0e",
            text_color="#f4f4f5",
            border_width=1,
            border_color="#1a1a22",
            corner_radius=6
        )
        self.console.grid(row=1, column=0, sticky="nsew")
        self.console.configure(state="disabled")

        # Configure Tkinter tags for styling logs inside the underlying Text widget
        text_widget = self.console._textbox
        text_widget.tag_config("timestamp", foreground="#52525b")
        text_widget.tag_config("INFO", foreground="#34d399", font=("Consolas", 11, "bold"))
        text_widget.tag_config("WARNING", foreground="#fbbf24", font=("Consolas", 11, "bold"))
        text_widget.tag_config("ERROR", foreground="#f87171", font=("Consolas", 11, "bold"))
        text_widget.tag_config("CRITICAL", foreground="#f87171", font=("Consolas", 11, "bold"))
        text_widget.tag_config("DEBUG", foreground="#60a5fa", font=("Consolas", 11, "bold"))
        text_widget.tag_config("default", foreground="#e4e4e7")

    def check_queue(self):
        # Read all available messages from the queue
        while True:
            try:
                msg, level = queue_log_handler.log_queue.get_nowait()
                self.append_log(msg, level)
            except queue.Empty:
                break
        
        # Schedule next check
        self.after(100, self.check_queue)

    def append_log(self, message: str, level: str):
        self.console.configure(state="normal")
        
        # Format logs: split by delimiter
        parts = message.split(" - ")
        if len(parts) >= 4:
            timestamp = parts[0].split(" ")[1] if " " in parts[0] else parts[0]
            actual_msg = " - ".join(parts[3:])
            
            # Append styled parts
            self.console.insert("end", f"[{timestamp}] ", "timestamp")
            self.console.insert("end", f"[{level}] ", level)
            self.console.insert("end", f"{actual_msg}\n", "default")
        else:
            self.console.insert("end", f"{message}\n", level if level in ["INFO", "WARNING", "ERROR", "CRITICAL", "DEBUG"] else "default")
        
        self.console.see("end")
        self.console.configure(state="disabled")

    def clear_logs(self):
        self.console.configure(state="normal")
        self.console.delete("1.0", "end")
        self.console.configure(state="disabled")

    def refresh_theme_colors(self, theme):
        colors = theme["colors"]
        self.console.configure(
            fg_color=colors["logBg"],
            text_color=colors["logText"],
            border_color=colors["border"]
        )
        self.clear_btn.configure(
            fg_color=colors["surface2"],
            hover_color=colors["border"],
            text_color=colors["textSecondary"]
        )
        self.title.configure(text_color=colors["textSecondary"])
