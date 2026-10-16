"""Coalesce width changes; never reconfigure wrapping for height-only events."""


class WrappedLabels:
    def __init__(self, container, labels, *, padding=28, minimum=100):
        self.container, self.labels = container, labels
        self.padding, self.minimum = padding, minimum
        self.width = None
        self.job = None
        self.closed = False
        container.bind("<Configure>", self.resize, add="+")
        container.bind("<Destroy>", self.destroy, add="+")

    def resize(self, event):
        if self.closed or event.widget not in (self.container, getattr(self.container, "_canvas", None)) or event.width <= 1:
            return
        width = max(self.minimum, int(self.container._reverse_widget_scaling(event.width)) - self.padding)
        if width == self.width:
            return
        self.width = width
        if self.job is not None:
            self.container.after_cancel(self.job)
        self.job = self.container.after(80, self.apply)

    def apply(self):
        self.job = None
        if not self.closed:
            for label in self.labels:
                if label.cget("wraplength") != self.width:
                    label.configure(wraplength=self.width)

    def destroy(self, event):
        if event.widget in (self.container, getattr(self.container, "_canvas", None)):
            self.closed = True
            if self.job is not None:
                self.container.after_cancel(self.job)
                self.job = None
