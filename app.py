import customtkinter as ctk

from ui.theme import COLORS, install_theme
from ui.sidebar import Sidebar
from ui.home import HomePage
from ui.dashboard import DashboardPage
from ui.prototype_studio import PrototypeStudioPage
from ui.prototype_logic import PrototypeSession
from ui.lead_workspace import LeadWorkspacePage
from ui.places_search import PlacesSearchPage
from ui.my_day import MyDayPage

install_theme()


class LoungLeadsApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Loung Prospect")
        self.geometry("1280x760")
        self.minsize(1050, 650)
        self.configure(fg_color=COLORS["bg"])
        self.prototype_session = PrototypeSession()

        self.sidebar = Sidebar(
            self,
            on_dashboard=self.show_dashboard,
            on_search=self.show_search,
            on_prototype=self.show_prototype,
            on_workspace=self.show_workspace,
            on_places=self.show_places,
            on_day=self.show_day,
        )
        self.sidebar.pack(side="left", fill="y")

        self.content = ctk.CTkFrame(self, fg_color=COLORS["bg"], corner_radius=0)
        self.content.pack(side="right", fill="both", expand=True)

        self.show_dashboard()

    def clear_content(self):
        for widget in self.content.winfo_children():
            widget.destroy()

    def show_dashboard(self):
        self.clear_content()
        self.sidebar.set_active("dashboard")
        DashboardPage(self.content, on_search=self.show_places, on_workspace=self.show_workspace, on_day=self.show_day).pack(fill="both", expand=True)

    def show_search(self):
        self.clear_content()
        self.sidebar.set_active("search")
        HomePage(self.content).pack(fill="both", expand=True)

    def show_prototype(self):
        self.clear_content()
        self.sidebar.set_active("prototype")
        PrototypeStudioPage(self.content, self.prototype_session).pack(fill="both", expand=True)

    def show_workspace(self, lead_id=None):
        self.clear_content()
        self.sidebar.set_active("workspace")
        page = LeadWorkspacePage(self.content)
        page.pack(fill="both", expand=True)
        if lead_id is not None:
            page.open_detail(lead_id)

    def show_day(self):
        self.clear_content()
        self.sidebar.set_active("day")
        MyDayPage(self.content, on_open=self.show_workspace).pack(fill="both", expand=True)

    def show_places(self):
        self.clear_content()
        self.sidebar.set_active("places")
        PlacesSearchPage(self.content, on_workspace=self.show_workspace).pack(fill="both", expand=True)
