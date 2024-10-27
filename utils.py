import tkinter as tk
from PIL import ImageGrab, ImageTk

class RegionSelector:
    """
    Allows the user to select a region on the screen by dragging the mouse over a screenshot.
    """
    def __init__(self):
        self.start_x = None
        self.start_y = None
        self.rect = None
        self.region = None
        self.root = None
        self.canvas = None
        self.image = None

    def select_region(self):
        # Take a screenshot
        screenshot = ImageGrab.grab()
        self.image = ImageTk.PhotoImage(screenshot)

        self.root = tk.Tk()
        self.root.attributes('-fullscreen', True)
        self.root.attributes('-topmost', True)
        self.root.overrideredirect(True)
        self.canvas = tk.Canvas(self.root, cursor="cross")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Display the screenshot
        self.canvas.create_image(0, 0, image=self.image, anchor=tk.NW)

        # Bind events
        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_move_press)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)
        self.root.mainloop()
        return self.region

    def on_button_press(self, event):
        # Save the starting point
        self.start_x = event.x
        self.start_y = event.y
        # Create a rectangle
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline='red', width=2)

    def on_move_press(self, event):
        # Update the rectangle as the mouse is dragged
        cur_x, cur_y = event.x, event.y
        # Expand rectangle as you drag the mouse
        self.canvas.coords(self.rect, self.start_x, self.start_y, cur_x, cur_y)

    def on_button_release(self, event):
        # Finalize the region selection
        end_x, end_y = event.x, event.y
        x1 = min(self.start_x, end_x)
        y1 = min(self.start_y, end_y)
        x2 = max(self.start_x, end_x)
        y2 = max(self.start_y, end_y)
        self.region = (int(x1), int(y1), int(x2 - x1), int(y2 - y1))
        self.root.destroy()
