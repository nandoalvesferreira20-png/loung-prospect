import customtkinter as ctk

from ui.theme import COLORS
from ui.sidebar import Sidebar
from ui.home import HomePage
from ui.dashboard import DashboardPage
from ui.prototype_studio import PrototypeStudioPage
from ui.prototype_logic import PrototypeSession

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class LoungLeadsApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Loung Leads")
        self.geometry("1150x720")
        self.minsize(1050, 650)
        self.configure(fg_color=COLORS["bg"])
        self.prototype_session = PrototypeSession()

        self.sidebar = Sidebar(
            self,
            on_dashboard=self.show_dashboard,
            on_search=self.show_search,
            on_prototype=self.show_prototype,
        )
        self.sidebar.pack(side="left", fill="y")

        self.content = ctk.CTkFrame(self, fg_color=COLORS["bg"], corner_radius=0)
        self.content.pack(side="right", fill="both", expand=True)

        self.show_search()

    def clear_content(self):
        for widget in self.content.winfo_children():
            widget.destroy()

    def show_dashboard(self):
        self.clear_content()
        self.sidebar.set_active("dashboard")
        DashboardPage(self.content).pack(fill="both", expand=True)

    def show_search(self):
        self.clear_content()
        self.sidebar.set_active("search")
        HomePage(self.content).pack(fill="both", expand=True)

    def show_prototype(self):
        self.clear_content()
        self.sidebar.set_active("prototype")
        PrototypeStudioPage(self.content, self.prototype_session).pack(fill="both", expand=True)
