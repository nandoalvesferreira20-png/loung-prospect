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
from ui.sales_workspace import SalesWorkspacePage
from core.providers.environment import load_environment
from ui.sdr_diagnostics import event, timed, callback_error

install_theme()


class LoungLeadsApp(ctk.CTk):
    def __init__(self):
        load_environment()
        super().__init__()

        self.title("Loung Prospect")
        self.geometry("1280x760")
        self.minsize(1100, 650)
        self.configure(fg_color=COLORS["bg"])
        self.prototype_session = PrototypeSession()
        self.current_page = None

        self.sidebar = Sidebar(
            self,
            on_dashboard=self.show_dashboard,
            on_search=self.show_search,
            on_prototype=self.show_prototype,
            on_workspace=self.show_workspace,
            on_places=self.show_places,
            on_day=self.show_day,
            on_sales=self.show_sales,
        )
        self.sidebar.pack(side="left", fill="y")

        self.content = ctk.CTkFrame(self, fg_color=COLORS["bg"], corner_radius=0)
        self.content.pack(side="right", fill="both", expand=True)

        self.protocol("WM_DELETE_WINDOW", self.request_close)
        self.show_dashboard()

    def can_leave_page(self):
        page = self.current_page
        return page is None or not hasattr(page, "can_leave") or page.can_leave()

    def request_close(self):
        if self.can_leave_page():
            self.destroy()

    def clear_content(self):
        if not self.can_leave_page():
            return False
        if self.current_page is not None:
            self.current_page.destroy()
            self.current_page = None
        for widget in self.content.winfo_children():
            widget.destroy()
        return True

    def show_dashboard(self):
        if isinstance(self.current_page, DashboardPage):
            return
        if not self.clear_content():
            return
        self.sidebar.set_active("dashboard")
        self.current_page = DashboardPage(self.content, on_search=self.show_places, on_workspace=self.show_workspace, on_day=self.show_day, on_sales=self.show_sales)
        self.current_page.pack(fill="both", expand=True)

    def show_search(self):
        if isinstance(self.current_page, HomePage):
            return
        if not self.clear_content():
            return
        self.sidebar.set_active("search")
        self.current_page = HomePage(self.content)
        self.current_page.pack(fill="both", expand=True)

    def show_prototype(self):
        if isinstance(self.current_page, PrototypeStudioPage):
            return
        if not self.clear_content():
            return
        self.sidebar.set_active("prototype")
        self.current_page = PrototypeStudioPage(self.content, self.prototype_session)
        self.current_page.pack(fill="both", expand=True)

    def show_workspace(self, lead_id=None):
        if isinstance(self.current_page, LeadWorkspacePage):
            if lead_id is not None:
                self.current_page.open_detail(lead_id)
            return
        if not self.clear_content():
            return
        self.sidebar.set_active("workspace")
        page = self.current_page = LeadWorkspacePage(self.content)
        page.pack(fill="both", expand=True)
        if lead_id is not None:
            page.open_detail(lead_id)

    def show_day(self):
        if isinstance(self.current_page, MyDayPage):
            return
        if not self.clear_content():
            return
        self.sidebar.set_active("day")
        self.current_page = MyDayPage(self.content, on_open=self.show_workspace)
        self.current_page.pack(fill="both", expand=True)

    def show_places(self):
        if isinstance(self.current_page, PlacesSearchPage):
            return
        if not self.clear_content():
            return
        self.sidebar.set_active("places")
        self.current_page = PlacesSearchPage(self.content, on_workspace=self.show_workspace)
        self.current_page.pack(fill="both", expand=True)

    def show_sales(self):
        event("menu_sdr")
        if getattr(self, "_opening_sales", False) or any(isinstance(widget, SalesWorkspacePage)
                for widget in self.content.winfo_children()):
            return
        if not self.clear_content():
            return
        self._opening_sales = True
        try:
            self.sidebar.set_active("sales")
            with timed("screen_construct"):
                self.current_page = SalesWorkspacePage(self.content)
                self.current_page.pack(fill="both", expand=True)
        finally:
            self._opening_sales = False

    def report_callback_exception(self, error_type, error, tb):
        callback_error(error_type, error, tb)
