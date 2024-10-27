# overlay.py

import tkinter as tk
import platform

class OverlayWindow:
    """
    Displays an overlay window with a border around the selected region.
    Changes border color based on monitoring status.
    """
    def __init__(self, region):
        self.region = region  # (x, y, width, height)
        self.root = tk.Tk()
        self.root.attributes("-topmost", True)
        self.root.overrideredirect(True)
        self.root.geometry(f"{region[2]}x{region[3]}+{region[0]}+{region[1]}")
        self.root.lift()
        self.canvas = tk.Canvas(self.root, width=region[2], height=region[3], highlightthickness=0)
        self.canvas.pack()
        self.border_color = 'red'
        self.draw_border()
        # Set window attributes to minimize interference
        if platform.system() == 'Windows':
            self.root.attributes('-transparentcolor', 'white')
            self.root.wm_attributes('-disabled', True)
        elif platform.system() == 'Darwin':
            # Additional attributes for macOS can be added if needed
            pass

    def draw_border(self):
        self.canvas.delete("all")
        self.canvas.configure(bg='white')
        self.canvas.create_rectangle(0, 0, self.region[2], self.region[3], outline=self.border_color, width=2)
        self.root.update_idletasks()

    def set_border_color(self, color):
        self.border_color = color
        self.draw_border()

    def show(self):
        self.root.deiconify()

    def hide(self):
        self.root.withdraw()

    def destroy(self):
        self.root.destroy()
