"""本地窗口：贴上入侵协议截图，标出上传路线。"""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageDraw, ImageFont, ImageGrab, ImageTk

from recognize import is_uncertain, recognize
from solver import CODES, solve

# 界面颜色，贴近游戏里的黄绿色
BG = "#10140f"  # 窗口底色
PANEL = "#1a2116"  # 右侧面板
TEXT = "#e4f2a8"  # 普通文字
ACCENT = "#d6ff4a"  # 路线高亮
WARN = "#ff5c4d"  # 识别不稳的格子

# 界面文案。键相同，zh / en 各一份
TEXT_STRINGS = {
    "zh": {
        "title": "赛博朋克 2077 入侵协议",
        "open": "打开截图",
        "paste": "粘贴截图  Ctrl+V",
        "buffer": "缓冲格数",
        "buffer_unsure": "缓冲格数（没数清，请核对）",
        "recalc": "重新计算",
        "pin": "窗口置顶",
        "unpin": "取消置顶",
        "full": "完整图",
        "wheel": "滚轮缩放，按住拖动",
        "edit_hint": "认错的格子直接改，红框表示这格不太稳",
        "switch": "English",
        "matrix": "代码矩阵",
        "sequences": "目标序列",
        "welcome": "打开一张入侵协议截图，或先截图再按 Ctrl+V。\n算出路线后会先对准矩阵，滚轮可以放大缩小，点「完整图」回到整张截图。",
        "canvas_empty": "把入侵协议的截图贴到这里\n滚轮缩放，按住拖动",
        "file_title": "选择入侵协议截图",
        "images": "图片",
        "all_files": "全部文件",
        "cannot_open": "打不开",
        "no_image_title": "没有图片",
        "no_image": "剪贴板里没有截图。可以先用系统截图复制，再按 Ctrl+V。",
        "no_matrix_title": "没有识别到矩阵",
        "no_codes": "没有走出任何代码。",
        "route": "路线：%s",
        "steps": "步数：%d / 缓冲 %d",
        "step": "%d. 第%d行 第%d列  %s",
        "buffer_left": "缓冲区还没走满。这些步骤走完，该上传的就已经上传了，剩下的格子随便点。",
        "uploaded": "已上传：%s",
        "missed": "未上传：%s",
        "none": "无",
        "join": "、",
    },
    "en": {
        "title": "Cyberpunk 2077 Breach Protocol",
        "open": "Open screenshot",
        "paste": "Paste screenshot  Ctrl+V",
        "buffer": "Buffer size",
        "buffer_unsure": "Buffer size (not counted, please check)",
        "recalc": "Recalculate",
        "pin": "Keep on top",
        "unpin": "Stop keeping on top",
        "full": "Full image",
        "wheel": "Scroll to zoom, drag to move",
        "edit_hint": "Correct a wrong cell directly. A red frame means it is uncertain",
        "switch": "中文",
        "matrix": "Code matrix",
        "sequences": "Target sequences",
        "welcome": "Open a breach protocol screenshot, or copy one and press Ctrl+V.\nAfter a route is found, the view frames the matrix. Scroll to zoom, and use Full image to see the whole screenshot.",
        "canvas_empty": "Paste a breach protocol screenshot here\nScroll to zoom, drag to move",
        "file_title": "Choose a breach protocol screenshot",
        "images": "Images",
        "all_files": "All files",
        "cannot_open": "Cannot open",
        "no_image_title": "No image",
        "no_image": "The clipboard has no screenshot. Copy one with your screenshot tool, then press Ctrl+V.",
        "no_matrix_title": "No matrix found",
        "no_codes": "No codes were entered.",
        "route": "Route: %s",
        "steps": "Steps: %d / buffer %d",
        "step": "%d. Row %d, column %d  %s",
        "buffer_left": "The buffer is not full. After these steps, every sequence that can be uploaded is already uploaded. Click any remaining cells.",
        "uploaded": "Uploaded: %s",
        "missed": "Not uploaded: %s",
        "none": "none",
        "join": ", ",
    },
}

# 求解和识别抛出的中文错误，切到英文时对照这张表
ERROR_EN = {
    "代码矩阵必须是方形": "The code matrix must be square.",
    "缓冲区长度至少为 1": "The buffer must hold at least 1 code.",
    "没有在截图里找到代码矩阵": "No code matrix was found in this screenshot.",
    "缺少字形模板，请先用参考截图生成 templates.npz": "Glyph templates are missing. Generate templates.npz from a reference screenshot first.",
}


def translate_error(lang, message):
    """把程序内部的中文错误换成当前语言。"""
    if lang == "zh":
        return message
    if message in ERROR_EN:
        return ERROR_EN[message]
    prefix = "无法识别的代码："
    if message.startswith(prefix):
        return "Unrecognized code: %s" % message[len(prefix):]
    return message


def annotate(image, result, route):
    """在截图上画出步骤编号，返回一张新图。"""
    canvas = image.convert("RGB").copy()  # 不改原图
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 16)  # 步骤数字
    except OSError:
        font = ImageFont.load_default()
    points = []  # 每一步的中心点
    for row, col in route["path"]:
        x0, y0, x1, y1 = result.matrix[row][col].box
        points.append(((x0 + x1) // 2, (y0 + y1) // 2))
    if len(points) >= 2:
        draw.line(points, fill=ACCENT, width=2)
    for step, (row, col) in enumerate(route["path"], start=1):
        x0, y0, x1, y1 = result.matrix[row][col].box
        cx = (x0 + x1) // 2
        cy = (y0 + y1) // 2
        radius = max(10, (x1 - x0) // 3)
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill="#111111", outline=ACCENT, width=2)
        label = str(step)
        bbox = draw.textbbox((0, 0), label, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw.text((cx - tw / 2, cy - th / 2 - 1), label, fill=ACCENT, font=font)
    return canvas


def describe_route(route, buffer_size, text):
    """把路线写成可以直接照着点的文字。text 是当前语言的文案表。"""
    if not route["codes"]:
        return text["no_codes"]
    lines = [text["route"] % " → ".join(route["codes"]), ""]
    lines.append(text["steps"] % (len(route["codes"]), buffer_size))
    lines.append("")
    for step, ((row, col), code) in enumerate(zip(route["path"], route["codes"]), start=1):
        lines.append(text["step"] % (step, row + 1, col + 1, code))
    if len(route["codes"]) < buffer_size:
        lines.append("")
        lines.append(text["buffer_left"])
    return "\n".join(lines)


class App:
    """截图求解窗口。"""

    def __init__(self):
        self.root = tk.Tk()  # 主窗口
        self.root.title(TEXT_STRINGS["zh"]["title"])
        self.root.geometry("1480x920")
        self.root.configure(bg=BG)
        self.root.minsize(1100, 720)

        self.image = None  # 当前截图
        self.result = None  # 识别结果
        self.route = None  # 求解结果
        self.photo = None  # 画布上的图片，必须留着引用
        self.loading = False  # 正在填格子时不要重复求解
        self.matrix_vars = []  # 矩阵里每个下拉框的变量
        self.matrix_frames = []  # 用来标红的外框
        self.sequence_vars = []  # 每条序列的下拉框
        self.lang = "zh"  # 当前界面语言
        self.pinned = False  # 窗口是否置顶
        self.pending_error = None  # 最近一次中文错误，切语言时再翻译
        self.buffer_var = tk.StringVar(value="8")  # 缓冲区格数
        self.buffer_hint = tk.StringVar(value=TEXT_STRINGS["zh"]["buffer"])  # 缓冲是否数清
        self.view_mode = "fit"  # fit 完整图，matrix 对准矩阵，free 用户缩放
        self.scale = 1.0  # 自由缩放时，一个截图像素占多少屏幕像素
        self.pan_x = 0.0  # 截图左上角在画布上的横坐标
        self.pan_y = 0.0  # 截图左上角在画布上的纵坐标
        self._drag_origin = None  # 正在拖动时的鼠标位置
        self._frame_next = False  # 下次算出路线后先对准矩阵

        self._build()
        self.root.bind("<Control-v>", lambda _event: self.paste_image())

    def _build(self):
        """摆好工具条、截图区和编辑区。"""
        bar = tk.Frame(self.root, bg=BG)
        bar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=(10, 0))
        self.open_button = tk.Button(bar, text="", command=self.open_file)
        self.open_button.pack(side="left")
        self.paste_button = tk.Button(bar, text="", command=self.paste_image)
        self.paste_button.pack(side="left", padx=8)
        tk.Label(bar, textvariable=self.buffer_hint, bg=BG, fg=TEXT).pack(side="left", padx=(16, 4))
        self.buffer_spin = tk.Spinbox(
            bar, from_=2, to=12, width=4, textvariable=self.buffer_var, command=self._on_edit
        )
        self.buffer_spin.pack(side="left")
        self.recalc_button = tk.Button(bar, text="", command=self._on_edit)
        self.recalc_button.pack(side="left", padx=8)
        self.pin_button = tk.Button(bar, text="", command=self._toggle_pin)  # 置顶开关
        self.pin_button.pack(side="left", padx=4)
        self.full_button = tk.Button(bar, text="", command=self._show_full)
        self.full_button.pack(side="left", padx=4)
        self.lang_button = tk.Button(bar, text="", command=self._toggle_language)  # 中英切换
        self.lang_button.pack(side="left", padx=4)
        self.wheel_label = tk.Label(bar, text="", bg=BG, fg="#8d9870")
        self.wheel_label.pack(side="left", padx=8)
        self.edit_label = tk.Label(bar, text="", bg=BG, fg="#8d9870")
        self.edit_label.pack(side="right")

        self.canvas = tk.Canvas(self.root, bg="#050705", highlightthickness=0)  # 左侧截图
        self.canvas.grid(row=1, column=0, sticky="nsew", padx=(12, 6), pady=12)
        self.canvas.bind("<Configure>", lambda _event: self._draw())
        self.canvas.bind("<MouseWheel>", self._on_wheel)
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)

        side = tk.Frame(self.root, bg=PANEL)  # 右侧矩阵和路线
        side.grid(row=1, column=1, sticky="nsew", padx=(6, 12), pady=12)
        side.grid_rowconfigure(2, weight=1)
        side.grid_columnconfigure(0, weight=1)
        self.matrix_label = tk.Label(side, text="", bg=PANEL, fg=ACCENT)
        self.matrix_label.grid(row=0, column=0, sticky="w", padx=8, pady=(8, 0))
        self.matrix_host = tk.Frame(side, bg=PANEL)
        self.matrix_host.grid(row=1, column=0, sticky="ew", padx=8, pady=4)
        self.sequence_label = tk.Label(side, text="", bg=PANEL, fg=ACCENT)
        self.sequence_label.grid(row=2, column=0, sticky="nw", padx=8)
        self.sequence_host = tk.Frame(side, bg=PANEL)
        self.sequence_host.grid(row=3, column=0, sticky="ew", padx=8, pady=4)
        self.route_text = tk.Text(
            side, height=16, bg="#0d120c", fg=TEXT, insertbackground=TEXT,
            relief="flat", wrap="word", font=("Microsoft YaHei UI", 11),
        )
        self.route_text.grid(row=4, column=0, sticky="nsew", padx=8, pady=(4, 8))
        side.grid_rowconfigure(4, weight=1)
        self._refresh_chrome()
        self._set_route_text(self._text("welcome"))

        self.root.grid_columnconfigure(0, weight=5)
        self.root.grid_columnconfigure(1, weight=2)
        self.root.grid_rowconfigure(1, weight=1)

    def _text(self, key):
        """取出当前语言的一句界面文案。"""
        return TEXT_STRINGS[self.lang][key]

    def _toggle_language(self):
        """在中文和英文界面之间切换，并重写已经显示的路线。"""
        self.lang = "en" if self.lang == "zh" else "zh"
        self._refresh_chrome()
        if self.result is not None:
            self._frame_next = False
            self._solve_current()
        elif self.pending_error:
            self._set_route_text(translate_error(self.lang, self.pending_error))
        else:
            self._set_route_text(self._text("welcome"))
        self._draw()

    def _refresh_chrome(self):
        """按当前语言刷新标题、按钮和固定标签。"""
        self.root.title(self._text("title"))
        self.open_button.configure(text=self._text("open"))
        self.paste_button.configure(text=self._text("paste"))
        self.recalc_button.configure(text=self._text("recalc"))
        self.pin_button.configure(text=self._text("unpin") if self.pinned else self._text("pin"))
        self.full_button.configure(text=self._text("full"))
        self.lang_button.configure(text=self._text("switch"))
        self.wheel_label.configure(text=self._text("wheel"))
        self.edit_label.configure(text=self._text("edit_hint"))
        self.matrix_label.configure(text=self._text("matrix"))
        self.sequence_label.configure(text=self._text("sequences"))
        if self.result is None:
            self.buffer_hint.set(self._text("buffer"))
        elif self.result.buffer_ok:
            self.buffer_hint.set(self._text("buffer"))
        else:
            self.buffer_hint.set(self._text("buffer_unsure"))

    def _toggle_pin(self):
        """让窗口保持在游戏画面前面，再按一次就取消。"""
        self.pinned = not self.pinned
        self.root.attributes("-topmost", self.pinned)
        self.pin_button.configure(text=self._text("unpin") if self.pinned else self._text("pin"))
        if self.pinned:
            self.root.lift()

    def _matrix_bounds(self):
        """算出代码矩阵在截图上的范围，四周留出步骤圆点的空位。"""
        if self.image is None or self.result is None or not self.route or not self.route["path"]:
            return None
        boxes = [cell.box for row in self.result.matrix for cell in row]  # 每一格的范围
        if not boxes:
            return None
        x0 = min(box[0] for box in boxes)
        y0 = min(box[1] for box in boxes)
        x1 = max(box[2] for box in boxes)
        y1 = max(box[3] for box in boxes)
        cell_w = max(12, int((x1 - x0) / max(1, len(self.result.matrix[0]))))  # 大约一格的宽度
        pad = int(cell_w * 0.9)
        x0 = max(0, x0 - pad)
        y0 = max(0, y0 - pad)
        x1 = min(self.image.width - 1, x1 + pad)
        y1 = min(self.image.height - 1, y1 + pad)
        if x1 <= x0 or y1 <= y0:
            return None
        return x0, y0, x1, y1

    def _show_full(self):
        """回到能看清整张截图的缩放。"""
        self.view_mode = "fit"
        self._draw()

    def _fit_scale(self, canvas_w, canvas_h):
        """整张截图刚好放进画布时的缩放。"""
        return min(canvas_w / self.image.width, canvas_h / self.image.height)

    def _view_params(self, canvas_w, canvas_h):
        """当前画面的缩放，以及截图左上角在画布上的位置。"""
        fit = self._fit_scale(canvas_w, canvas_h)  # 完整图的缩放
        if self.view_mode == "free":
            return self.scale, self.pan_x, self.pan_y
        if self.view_mode == "matrix":
            bounds = self._matrix_bounds()
            if bounds:
                x0, y0, x1, y1 = bounds
                box_w = x1 - x0 + 1  # 矩阵区域宽度
                box_h = y1 - y0 + 1
                scale = min(canvas_w / box_w, canvas_h / box_h)
                pan_x = (canvas_w - box_w * scale) / 2 - x0 * scale
                pan_y = (canvas_h - box_h * scale) / 2 - y0 * scale
                return scale, pan_x, pan_y
        pan_x = (canvas_w - self.image.width * fit) / 2
        pan_y = (canvas_h - self.image.height * fit) / 2
        return fit, pan_x, pan_y

    def _clamp_pan(self, canvas_w, canvas_h):
        """别把图拖到画布外面，缩得比窗口小时就居中。"""
        img_w = self.image.width * self.scale  # 图在屏幕上的宽
        img_h = self.image.height * self.scale
        if img_w <= canvas_w:
            self.pan_x = (canvas_w - img_w) / 2
        else:
            self.pan_x = min(0, max(self.pan_x, canvas_w - img_w))
        if img_h <= canvas_h:
            self.pan_y = (canvas_h - img_h) / 2
        else:
            self.pan_y = min(0, max(self.pan_y, canvas_h - img_h))

    def _on_wheel(self, event):
        """以鼠标位置为中心放大或缩小。缩到最小就是完整图。"""
        if self.image is None or event.delta == 0:
            return
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()
        if canvas_w < 30 or canvas_h < 30:
            return
        scale, pan_x, pan_y = self._view_params(canvas_w, canvas_h)
        fit = self._fit_scale(canvas_w, canvas_h)
        factor = 1.12 if event.delta > 0 else 1 / 1.12  # 滚轮一格的倍率
        image_x = (event.x - pan_x) / scale  # 鼠标下面的截图坐标
        image_y = (event.y - pan_y) / scale
        new_scale = scale * factor
        max_scale = max(fit * 14, 6)
        if new_scale <= fit * 1.03:
            self.view_mode = "fit"
        else:
            self.view_mode = "free"
            self.scale = min(new_scale, max_scale)
            self.pan_x = event.x - image_x * self.scale
            self.pan_y = event.y - image_y * self.scale
            self._clamp_pan(canvas_w, canvas_h)
        self._draw()

    def _on_press(self, event):
        """开始拖动画面。"""
        if self.image is None:
            return
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()
        if canvas_w < 30 or canvas_h < 30:
            return
        scale, pan_x, pan_y = self._view_params(canvas_w, canvas_h)
        self.view_mode = "free"
        self.scale = scale
        self.pan_x = pan_x
        self.pan_y = pan_y
        self._drag_origin = (event.x, event.y)

    def _on_drag(self, event):
        """按住左键平移，用来查看完整图被挡住的部分。"""
        if self._drag_origin is None or self.image is None:
            return
        origin_x, origin_y = self._drag_origin
        self.pan_x += event.x - origin_x
        self.pan_y += event.y - origin_y
        self._drag_origin = (event.x, event.y)
        self._clamp_pan(self.canvas.winfo_width(), self.canvas.winfo_height())
        self._draw()

    def open_file(self):
        """从文件打开截图。"""
        path = filedialog.askopenfilename(
            title=self._text("file_title"),
            filetypes=[(self._text("images"), "*.png *.jpg *.jpeg *.bmp *.webp"), (self._text("all_files"), "*.*")],
        )
        if not path:
            return
        try:
            image = Image.open(path)
        except OSError as exc:
            messagebox.showerror(self._text("cannot_open"), str(exc))
            return
        self.load_image(image)

    def paste_image(self):
        """从剪贴板粘贴截图。"""
        data = ImageGrab.grabclipboard()
        if isinstance(data, Image.Image):
            self.load_image(data)
            return
        if isinstance(data, list) and data:
            try:
                self.load_image(Image.open(data[0]))
            except OSError as exc:
                messagebox.showerror(self._text("cannot_open"), str(exc))
            return
        messagebox.showinfo(self._text("no_image_title"), self._text("no_image"))

    def load_image(self, image):
        """识别这张截图并算出路线。"""
        self.image = image.convert("RGB")
        self.view_mode = "fit"
        self._frame_next = True
        self.pending_error = None
        try:
            self.result = recognize(self.image)
        except ValueError as exc:
            self.result = None
            self.route = None
            self._frame_next = False
            self.pending_error = str(exc)
            self._set_route_text(translate_error(self.lang, self.pending_error))
            self._draw()
            messagebox.showerror(self._text("no_matrix_title"), translate_error(self.lang, self.pending_error))
            return
        self._fill_editors()
        self._solve_current()

    def _clear(self, host):
        """清掉一块面板里的旧控件。"""
        for child in host.winfo_children():
            child.destroy()

    def _fill_editors(self):
        """把识别结果填进可修改的下拉框。"""
        self.loading = True
        self._clear(self.matrix_host)
        self._clear(self.sequence_host)
        self.matrix_vars = []
        self.matrix_frames = []
        self.sequence_vars = []
        for row_cells in self.result.matrix:
            row_vars = []
            row_frames = []
            line = tk.Frame(self.matrix_host, bg=PANEL)
            line.pack(anchor="w", pady=1)
            for cell in row_cells:
                low = is_uncertain(cell.confidence)  # 这格认不稳
                frame = tk.Frame(line, bg=WARN if low else PANEL, padx=1, pady=1)
                frame.pack(side="left", padx=1)
                var = tk.StringVar(value=cell.code)
                combo = ttk.Combobox(frame, textvariable=var, values=CODES, width=4, state="readonly")
                combo.pack()
                combo.bind("<<ComboboxSelected>>", lambda _event, box=frame: self._mark_edited(box))
                row_vars.append(var)
                row_frames.append(frame)
            self.matrix_vars.append(row_vars)
            self.matrix_frames.append(row_frames)
        for sequence in self.result.sequences:
            row_vars = []
            line = tk.Frame(self.sequence_host, bg=PANEL)
            line.pack(anchor="w", pady=1)
            for cell in sequence:
                low = is_uncertain(cell.confidence)
                frame = tk.Frame(line, bg=WARN if low else PANEL, padx=1, pady=1)
                frame.pack(side="left", padx=1)
                var = tk.StringVar(value=cell.code)
                combo = ttk.Combobox(frame, textvariable=var, values=CODES, width=4, state="readonly")
                combo.pack()
                combo.bind("<<ComboboxSelected>>", lambda _event, box=frame: self._mark_edited(box))
                row_vars.append(var)
            self.sequence_vars.append(row_vars)
        self.buffer_var.set(str(self.result.buffer_size))
        if self.result.buffer_ok:
            self.buffer_hint.set(self._text("buffer"))
        else:
            self.buffer_hint.set(self._text("buffer_unsure"))
        self.loading = False

    def _mark_edited(self, frame):
        """手改过的格子去掉红框，再重新计算。"""
        frame.configure(bg=PANEL)
        self._on_edit()

    def _on_edit(self):
        """下拉框或缓冲格数变了，就重算。"""
        if self.loading or self.result is None:
            return
        self._solve_current()

    def _read_board(self):
        """读出界面上当前的矩阵、序列和缓冲格数。"""
        matrix = [[var.get() for var in row] for row in self.matrix_vars]
        sequences = []  # 每条序列的代码
        for row in self.sequence_vars:
            sequence = [var.get() for var in row if var.get()]
            if sequence:
                sequences.append(sequence)
        buffer_size = int(self.buffer_var.get())
        return matrix, sequences, buffer_size

    def _solve_current(self):
        """按界面上的棋盘求一条路线。"""
        matrix, sequences, buffer_size = self._read_board()
        try:
            self.route = solve(matrix, sequences, buffer_size)
        except ValueError as exc:
            self.route = None
            self.pending_error = str(exc)
            self._set_route_text(translate_error(self.lang, self.pending_error))
            self._draw()
            return
        self.pending_error = None
        names = []  # 完成了哪些序列
        missed = []  # 没完成的序列
        for index, sequence in enumerate(sequences):
            text = " ".join(sequence)
            if index in self.route["completed"]:
                names.append(text)
            else:
                missed.append(text)
        words = self._text
        body = describe_route(self.route, buffer_size, TEXT_STRINGS[self.lang])
        extra = ["", words("uploaded") % (words("join").join(names) if names else words("none"))]
        extra.append(words("missed") % (words("join").join(missed) if missed else words("none")))
        self._set_route_text(body + "\n" + "\n".join(extra))
        if self._frame_next and self.route["path"]:
            self.view_mode = "matrix"
        self._frame_next = False
        self._draw()

    def _set_route_text(self, text):
        """替换右侧的路线说明。"""
        self.route_text.configure(state="normal")
        self.route_text.delete("1.0", "end")
        self.route_text.insert("1.0", text)
        self.route_text.configure(state="disabled")

    def _draw(self):
        """把截图和步骤编号画到左侧。"""
        self.canvas.delete("all")
        if self.image is None:
            self.canvas.create_text(
                20, 20, anchor="nw", fill="#8d9870",
                text=self._text("canvas_empty"), font=("Microsoft YaHei UI", 14),
            )
            return
        width = self.canvas.winfo_width()  # 画布宽
        height = self.canvas.winfo_height()  # 画布高
        if width < 30 or height < 30:
            return
        scale, pan_x, pan_y = self._view_params(width, height)
        img_w = self.image.width
        img_h = self.image.height
        left = max(0, int((-pan_x) / scale))  # 可见区域在截图上的左边界
        top = max(0, int((-pan_y) / scale))
        right = min(img_w, int((width - pan_x) / scale) + 2)
        bottom = min(img_h, int((height - pan_y) / scale) + 2)
        if right <= left or bottom <= top:
            return
        source = self.image.crop((left, top, right, bottom))
        show_w = max(1, int((right - left) * scale))
        show_h = max(1, int((bottom - top) * scale))
        shown = source.resize((show_w, show_h), Image.Resampling.NEAREST if scale >= 1.4 else Image.Resampling.BILINEAR)
        self.photo = ImageTk.PhotoImage(shown)
        self.canvas.create_image(pan_x + left * scale, pan_y + top * scale, anchor="nw", image=self.photo)
        if not self.result or not self.route:
            return
        points = []  # 画布上的步骤中心
        for row, col in self.route["path"]:
            x0, y0, x1, y1 = self.result.matrix[row][col].box
            cx = pan_x + (x0 + x1) / 2 * scale
            cy = pan_y + (y0 + y1) / 2 * scale
            points.append((cx, cy, x1 - x0))
        if len(points) >= 2:
            flat = [coord for cx, cy, _span in points for coord in (cx, cy)]
            self.canvas.create_line(*flat, fill=ACCENT, width=3)
        for step, (cx, cy, span) in enumerate(points, start=1):
            radius = max(14, span * scale * 0.38)
            self.canvas.create_oval(
                cx - radius, cy - radius, cx + radius, cy + radius,
                fill="#111111", outline=ACCENT, width=3,
            )
            self.canvas.create_text(
                cx, cy, text=str(step), fill=ACCENT,
                font=("Microsoft YaHei UI", max(14, int(radius * 0.85)), "bold"),
            )


def main():
    """打开窗口。"""
    app = App()
    app.root.mainloop()


if __name__ == "__main__":
    main()
