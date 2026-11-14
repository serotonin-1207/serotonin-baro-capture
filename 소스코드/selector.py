"""포커스 변경 전에 확보한 화면에서 영역을 선택한다."""
import tkinter as tk

from PIL import ImageTk


class ScreenSelector(tk.Toplevel):
    def __init__(self, root, snapshot, picked, closed):
        super().__init__(root)
        self.withdraw()
        self.snapshot, self.picked, self.closed = snapshot, picked, closed
        self.start = None
        width, height = snapshot.image.size
        x, y = snapshot.origin
        self.overrideredirect(True)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.attributes("-topmost", True)
        self.canvas = tk.Canvas(self, cursor="crosshair", bg="#172a36", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.photo = ImageTk.PhotoImage(snapshot.image, master=self)
        self.canvas.create_image(0, 0, image=self.photo, anchor="nw")
        self.canvas.bind("<ButtonPress-1>", self.begin)
        self.canvas.bind("<B1-Motion>", self.draw)
        self.canvas.bind("<ButtonRelease-1>", self.finish)
        self.bind("<Escape>", lambda event: self.destroy())
        self.bind("<Destroy>", self.on_close)
        self.deiconify()
        self.focus_force()

    def begin(self, event):
        self.start = (event.x_root, event.y_root)
        self.rectangle = self.canvas.create_rectangle(event.x, event.y, event.x, event.y,
                                                       outline="#248fd0", width=2)

    def draw(self, event):
        if self.start is not None:
            x, y = self.start
            ox, oy = self.snapshot.origin
            self.canvas.coords(self.rectangle, x-ox, y-oy, event.x, event.y)

    def finish(self, event):
        if self.start is None:
            return
        x, y = self.start
        left, right = sorted((x, event.x_root))
        top, bottom = sorted((y, event.y_root))
        snapshot = self.snapshot
        self.destroy()
        if right-left > 3 and bottom-top > 3:
            self.picked(snapshot, (left, top, right, bottom))

    def on_close(self, event):
        if event.widget is self:
            self.photo = None
            self.snapshot = None
            self.closed()
