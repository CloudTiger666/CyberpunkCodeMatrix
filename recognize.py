"""从入侵协议截图读出代码矩阵、目标序列和缓冲区长度。"""

import os

import numpy as np
from PIL import Image

from solver import CODES

# 字形比较用的固定尺寸，宽高比接近两个字母
GLYPH_W = 32  # 模板宽度
GLYPH_H = 18  # 模板高度
# 和 recognize.py 放在一起的模板文件
TEMPLATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates.npz")


class CellRead:
    """一个识别出来的代码格。"""

    def __init__(self, code, confidence, box):
        self.code = code  # 识别出的代码
        self.confidence = confidence  # 和第二名的差距，越大越稳
        self.box = box  # (左, 上, 右, 下)，截图像素坐标


class ReadResult:
    """一张截图的识别结果。"""

    def __init__(self, matrix, sequences, buffer_size, buffer_ok):
        self.matrix = matrix  # 二维 CellRead，matrix[行][列]
        self.sequences = sequences  # 每条序列是一列 CellRead
        self.buffer_size = buffer_size  # 缓冲区格数
        self.buffer_ok = buffer_ok  # 缓冲格数是否从空槽数出来了


def recognize(image):
    """读出截图里的矩阵、序列和缓冲区长度。"""
    rgb = _to_rgb(image)  # 统一成 RGB 数组
    grid = _find_matrix_grid(rgb)
    if grid is None:
        raise ValueError("没有在截图里找到代码矩阵")
    templates = _load_templates()
    matrix = []  # 识别后的矩阵
    for row_box in grid:
        row_cells = []
        for box in row_box:
            ink = _glyph_from_box(rgb, box)
            code, confidence = _classify(ink, templates)
            row_cells.append(CellRead(code, confidence, box))
        matrix.append(row_cells)
    sequences = _find_sequences(rgb, grid, templates)
    buffer_size, buffer_ok = _count_buffer(rgb)
    return ReadResult(matrix, sequences, buffer_size, buffer_ok)


def build_templates(image, matrix_codes):
    """用一张已经对过答案的截图生成六张字形模板。"""
    rgb = _to_rgb(image)
    grid = _find_matrix_grid(rgb)
    if grid is None or len(grid) != len(matrix_codes):
        raise ValueError("模板截图的矩阵对不上")
    samples = {code: [] for code in CODES}  # 每个代码收集到的字形
    for row_box, row_code in zip(grid, matrix_codes):
        if len(row_box) != len(row_code):
            raise ValueError("模板截图的列数对不上")
        for box, code in zip(row_box, row_code):
            samples[code].append(_glyph_from_box(rgb, box))
    stacked = {}
    for code, glyphs in samples.items():
        if not glyphs:
            raise ValueError("模板里缺少代码 %s" % code)
        stacked[code] = np.mean(glyphs, axis=0).astype(np.float32)
    np.savez(TEMPLATE_PATH, **stacked)


def _to_rgb(image):
    """把 PIL 图片转成 uint8 的 RGB 数组。"""
    rgb = image.convert("RGB")
    return np.asarray(rgb)


def _load_templates():
    """读入六张字形模板。"""
    if not os.path.exists(TEMPLATE_PATH):
        raise ValueError("缺少字形模板，请先用参考截图生成 templates.npz")
    data = np.load(TEMPLATE_PATH)
    return {code: data[code] for code in CODES}


def _yellow_mask(rgb, threshold):
    """挑出偏黄的笔画。threshold 越大，只留下越亮的黄。"""
    red = rgb[:, :, 0].astype(np.int16)  # 红色通道
    green = rgb[:, :, 1].astype(np.int16)  # 绿色通道
    blue = rgb[:, :, 2].astype(np.int16)  # 蓝色通道
    score = red + green - 2 * blue  # 黄色越高这个值越大
    return (score > threshold) & (red > 70) & (green > 60)


def _white_mask(rgb):
    """挑出序列区那种接近白色的笔画。"""
    red = rgb[:, :, 0].astype(np.int16)
    green = rgb[:, :, 1].astype(np.int16)
    blue = rgb[:, :, 2].astype(np.int16)
    return (red > 150) & (green > 150) & (blue > 130) & (np.abs(red - green) < 45) & (blue + 30 > red)


def _dilate(mask, radius_x, radius_y):
    """把笔画稍微加粗，让同一个代码的两个字母连到一起。"""
    grown = mask.copy()
    for shift in range(1, radius_x + 1):
        grown[:, shift:] |= mask[:, :-shift]
        grown[:, :-shift] |= mask[:, shift:]
    horizontal = grown.copy()
    for shift in range(1, radius_y + 1):
        grown[shift:, :] |= horizontal[:-shift, :]
        grown[:-shift, :] |= horizontal[shift:, :]
    return grown


def _components(mask):
    """连通域。返回 [左, 上, 右, 下, 像素数]。"""
    height = mask.shape[0]  # 图高
    parent = {}  # 并查集

    def find(node):
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(left, right):
        root_left = find(left)
        root_right = find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    runs = []  # 每一小段横条
    next_id = 0  # 下一段的编号
    previous = []  # 上一行的横条
    for y in range(height):
        xs = np.flatnonzero(mask[y])
        if len(xs) == 0:
            previous = []
            continue
        spans = []  # 这一行里连续的像素段
        start = int(xs[0])
        prev_x = int(xs[0])
        for x in xs[1:]:
            x = int(x)
            if x > prev_x + 1:
                spans.append((start, prev_x))
                start = x
            prev_x = x
        spans.append((start, prev_x))
        current = []
        for x0, x1 in spans:
            parent[next_id] = next_id
            for _py, px0, px1, pid in previous:
                if x1 >= px0 - 1 and x0 <= px1 + 1:
                    union(next_id, pid)
            current.append((y, x0, x1, next_id))
            next_id += 1
        previous = current
        runs.extend(current)

    boxes = {}  # 每个连通域的外接框
    for y, x0, x1, ident in runs:
        root = find(ident)
        box = boxes.get(root)
        width = x1 - x0 + 1
        if box is None:
            boxes[root] = [x0, y, x1, y, width]
        else:
            if x0 < box[0]:
                box[0] = x0
            if y < box[1]:
                box[1] = y
            if x1 > box[2]:
                box[2] = x1
            if y > box[3]:
                box[3] = y
            box[4] += width
    return list(boxes.values())


def _code_boxes(mask, typical=None):
    """从笔画蒙版里找出像代码一样大的小块，并把同一代码的字母合并。"""
    raw = _components(mask)
    if not raw:
        return []
    if typical is None:
        heights = [box[3] - box[1] + 1 for box in raw]
        typical = int(np.median(heights))  # 字母的典型高度
    typical = int(typical)
    if typical < 4:
        return []
    pieces = []  # 先丢掉细线和噪点
    for box in raw:
        box_h = box[3] - box[1] + 1
        box_w = box[2] - box[0] + 1
        if box_h < typical * 0.45 or box_h > typical * 2.4:
            continue
        if box_w > typical * 6:
            continue
        if box[4] < typical:
            continue
        pieces.append(box)
    return _merge_pieces(pieces, typical)


def _merge_pieces(pieces, typical):
    """同一行里靠得很近的字母合成一个代码。"""
    if not pieces:
        return []
    gap_limit = max(2, int(typical * 0.7))  # 小于这个缝就当成同一个代码
    y_tol = typical * 0.9  # 行中心差过这个值就换行
    ordered = sorted(pieces, key=lambda box: ((box[1] + box[3]) / 2, box[0]))
    rows = []  # 每一项是 (行中心, [盒子])
    for box in ordered:
        center_y = (box[1] + box[3]) / 2
        if rows and abs(center_y - rows[-1][0]) <= y_tol:
            rows[-1][1].append(box)
            count = len(rows[-1][1])
            rows[-1][0] = (rows[-1][0] * (count - 1) + center_y) / count
        else:
            rows.append([center_y, [box]])
    merged = []
    for _center, row_boxes in rows:
        row_boxes.sort(key=lambda box: box[0])
        current = list(row_boxes[0])
        for box in row_boxes[1:]:
            gap = box[0] - current[2] - 1
            if gap <= gap_limit:
                current[0] = min(current[0], box[0])
                current[1] = min(current[1], box[1])
                current[2] = max(current[2], box[2])
                current[3] = max(current[3], box[3])
                current[4] += box[4]
            else:
                merged.append(current)
                current = list(box)
        merged.append(current)
    codes = []  # 宽高像两个字母的块
    for box in merged:
        box_h = box[3] - box[1] + 1
        box_w = box[2] - box[0] + 1
        if box_w < typical * 0.7 or box_w > typical * 3.4:
            continue
        if box_h < typical * 0.55:
            continue
        codes.append(box)
    return codes


def _group_rows(boxes):
    """按纵向位置把盒子分成行。"""
    if not boxes:
        return []
    heights = [box[3] - box[1] + 1 for box in boxes]
    y_tol = max(4, int(np.median(heights)))
    ordered = sorted(boxes, key=lambda box: (box[1] + box[3]) / 2)
    rows = []
    for box in ordered:
        center_y = (box[1] + box[3]) / 2
        if rows and abs(center_y - rows[-1][0]) <= y_tol:
            rows[-1][1].append(box)
            count = len(rows[-1][1])
            rows[-1][0] = (rows[-1][0] * (count - 1) + center_y) / count
        else:
            rows.append([center_y, [box]])
    return rows


def _even_columns(row_boxes):
    """如果这一行的代码几乎等间距，返回列中心，否则返回 None。"""
    if len(row_boxes) < 4:
        return None
    centers = sorted((box[0] + box[2]) / 2 for box in row_boxes)
    gaps = [centers[i + 1] - centers[i] for i in range(len(centers) - 1)]
    pitch = float(np.median(gaps))
    if pitch < 8:
        return None
    # 锚点行必须整行等间距，远处的图标不能算进矩阵
    if any(abs(gap - pitch) > pitch * 0.45 for gap in gaps):
        return None
    return centers


def _find_matrix_grid(rgb):
    """找出代码矩阵每一格的像素范围。找不到时返回 None。"""
    height, width = rgb.shape[:2]
    radius_x = max(1, width // 450)  # 横向加粗，随分辨率变
    radius_y = max(1, height // 320)  # 纵向加粗
    best = None  # (格子数, 阈值, 网格)
    for threshold in (110, 90, 70):
        mask = _dilate(_yellow_mask(rgb, threshold), radius_x, radius_y)
        boxes = _code_boxes(mask)
        grid = _grid_from_boxes(boxes, rgb, threshold)
        if grid is None:
            continue
        cells = len(grid) * len(grid[0])
        if best is None or cells > best[0]:
            best = (cells, threshold, grid)
        if len(grid) == len(grid[0]) and len(grid) >= 4:
            return grid
    if best is None:
        return None
    return best[2]


def _grid_from_boxes(boxes, rgb, threshold):
    """用检测到的代码块推断完整的方形网格。"""
    rows = _group_rows(boxes)
    anchor = None  # (列间距, 列中心)
    for _center, row_boxes in rows:
        centers = _even_columns(row_boxes)
        if centers is None:
            continue
        if anchor is None or len(centers) > len(anchor[1]):
            gaps = [centers[i + 1] - centers[i] for i in range(len(centers) - 1)]
            anchor = (float(np.median(gaps)), centers)
    if anchor is None:
        return None
    pitch_x, col_centers = anchor
    matched_rows = []  # 落在这些列上的行中心
    for center_y, row_boxes in rows:
        hits = 0
        for box in row_boxes:
            center_x = (box[0] + box[2]) / 2
            if min(abs(center_x - col) for col in col_centers) <= pitch_x * 0.4:
                hits += 1
        if hits >= max(3, len(col_centers) // 2):
            matched_rows.append(center_y)
    if len(matched_rows) < 4:
        return None
    matched_rows.sort()
    gaps = [matched_rows[i + 1] - matched_rows[i] for i in range(len(matched_rows) - 1)]
    pitch_y = float(np.median(gaps))
    if pitch_y < 8:
        return None
    # 丢掉间距明显不对的杂行，只留最密的那一段
    chains = [[matched_rows[0]]]
    for previous, current in zip(matched_rows, matched_rows[1:]):
        gap = current - previous
        if abs(gap - pitch_y) <= pitch_y * 0.45 or abs(gap - 2 * pitch_y) <= pitch_y * 0.45:
            chains[-1].append(current)
        else:
            chains.append([current])
    row_centers = max(chains, key=len)
    filled = [row_centers[0]]  # 补上中间缺的一行
    for previous, current in zip(row_centers, row_centers[1:]):
        gap = current - previous
        if abs(gap - 2 * pitch_y) <= pitch_y * 0.45:
            filled.append(previous + gap / 2)
        filled.append(current)
    row_centers = filled
    row_centers = _square_up(row_centers, col_centers, pitch_y, rgb, threshold)
    if row_centers is None:
        return None
    return _cell_boxes(row_centers, col_centers, pitch_x, pitch_y, rgb.shape[1], rgb.shape[0])


def _square_up(row_centers, col_centers, pitch_y, rgb, threshold):
    """矩阵一定是正方形。差一行时，去上下两边找比较淡的那一行。"""
    target = len(col_centers)  # 目标行数
    centers = list(row_centers)
    mask = _yellow_mask(rgb, max(60, threshold - 30))

    def ink_at(center_y):
        total = 0
        half_x = pitch_y * 0.28
        half_y = pitch_y * 0.28
        for center_x in col_centers:
            x0 = int(center_x - half_x)
            x1 = int(center_x + half_x)
            y0 = int(center_y - half_y)
            y1 = int(center_y + half_y)
            if y0 < 0 or x0 < 0 or y1 >= mask.shape[0] or x1 >= mask.shape[1]:
                continue
            total += int(mask[y0:y1, x0:x1].sum())
        return total

    known = [ink_at(center) for center in centers]
    normal = float(np.median(known)) if known else 0
    while len(centers) < target:
        above = centers[0] - pitch_y
        below = centers[-1] + pitch_y
        above_ink = ink_at(above)
        below_ink = ink_at(below)
        if max(above_ink, below_ink) < normal * 0.28:
            return None
        if above_ink >= below_ink:
            centers.insert(0, above)
        else:
            centers.append(below)
    if len(centers) > target:
        best_window = None
        best_score = -1
        for start in range(len(centers) - target + 1):
            window = centers[start:start + target]
            gaps = [window[i + 1] - window[i] for i in range(len(window) - 1)]
            score = -float(np.std(gaps))
            if score > best_score:
                best_score = score
                best_window = window
        centers = best_window
    if len(centers) != target:
        return None
    return centers


def _cell_boxes(row_centers, col_centers, pitch_x, pitch_y, width, height):
    """按行列中心切出每一格，留一点边，避免切到隔壁。"""
    half_x = pitch_x * 0.40
    half_y = pitch_y * 0.36
    grid = []
    for center_y in row_centers:
        row = []
        for center_x in col_centers:
            x0 = max(0, int(round(center_x - half_x)))
            y0 = max(0, int(round(center_y - half_y)))
            x1 = min(width - 1, int(round(center_x + half_x)))
            y1 = min(height - 1, int(round(center_y + half_y)))
            row.append((x0, y0, x1, y1))
        grid.append(row)
    return grid


def _glyph_from_box(rgb, box):
    """把一格里的笔画收成固定大小的字形。"""
    x0, y0, x1, y1 = box
    crop = rgb[y0:y1 + 1, x0:x1 + 1]
    if crop.size == 0:
        return np.zeros((GLYPH_H, GLYPH_W), np.float32)
    red = crop[:, :, 0].astype(np.int16)
    green = crop[:, :, 1].astype(np.int16)
    blue = crop[:, :, 2].astype(np.int16)
    yellow = (red + green - 2 * blue) > 60
    white = (red > 140) & (green > 140) & (blue > 120)
    ink = yellow | white
    if int(ink.sum()) < 8:
        ink = (red + green - 2 * blue) > 35
    ys, xs = np.where(ink)
    if len(xs) < 8:
        return np.zeros((GLYPH_H, GLYPH_W), np.float32)
    tight = ink[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    image = Image.fromarray(tight.astype(np.uint8) * 255)
    image = image.resize((GLYPH_W, GLYPH_H), Image.Resampling.BILINEAR)
    return np.asarray(image).astype(np.float32) / 255.0


def _classify(ink, templates):
    """和六张模板比距离，返回代码和置信度。"""
    ranking = []  # (距离, 代码)
    for code in CODES:
        distance = float(np.mean(np.abs(ink - templates[code])))
        ranking.append((distance, code))
    ranking.sort()
    best_distance, best_code = ranking[0]
    second_distance = ranking[1][0]
    confidence = second_distance - best_distance
    if best_distance > 0.45:
        confidence = min(confidence, 0.01)
    return best_code, confidence


def _find_sequences(rgb, grid, templates):
    """在矩阵右边找白色的目标序列。"""
    matrix_right = max(cell[2] for row in grid for cell in row)  # 矩阵右边界
    matrix_top = min(cell[1] for row in grid for cell in row)
    matrix_bottom = max(cell[3] for row in grid for cell in row)
    cell_w = float(np.median([cell[2] - cell[0] for row in grid for cell in row]))
    cell_h = float(np.median([cell[3] - cell[1] for row in grid for cell in row]))
    # 序列字母比格子矮一截。用这个高度过滤，避免被界面上的小噪点带偏
    glyph_h = max(6, int(cell_h * 0.42))
    boxes = _code_boxes(_white_mask(rgb), typical=glyph_h)
    if len(boxes) < 2:
        boxes = _code_boxes(_yellow_mask(rgb, 90), typical=glyph_h)
    # 序列在矩阵右侧、高度和矩阵上半部分重叠
    nearby = []
    for box in boxes:
        center_x = (box[0] + box[2]) / 2
        center_y = (box[1] + box[3]) / 2
        box_w = box[2] - box[0] + 1
        box_h = box[3] - box[1] + 1
        if center_x < matrix_right + cell_w * 0.3:
            continue
        if center_y < matrix_top - cell_h * 1.6 or center_y > matrix_top + cell_h * 5.5:
            continue
        if box_w > cell_w * 1.7 or box_h > cell_h * 1.8:
            continue
        if center_y > matrix_bottom:
            continue
        nearby.append(box)
    rows = _group_rows(nearby)
    # 只要 2 到 4 个代码、并且左边对齐的那几行
    candidates = []
    for center_y, row_boxes in rows:
        if not 2 <= len(row_boxes) <= 4:
            continue
        row_boxes = sorted(row_boxes, key=lambda box: box[0])
        left = row_boxes[0][0]
        candidates.append((center_y, left, row_boxes))
    if not candidates:
        return []
    candidates.sort(key=lambda item: item[0])
    # 从最靠左的一列开始，把纵向排成一列的行收进来
    anchor_left = min(item[1] for item in candidates)
    chosen = []
    for center_y, left, row_boxes in candidates:
        if abs(left - anchor_left) > cell_w * 0.8:
            continue
        if chosen and center_y - chosen[-1][0] > cell_h * 3.2:
            break
        chosen.append((center_y, left, row_boxes))
    sequences = []
    for _center_y, _left, row_boxes in chosen:
        sequence = []
        for box in row_boxes:
            x0, y0, x1, y1 = box[0], box[1], box[2], box[3]
            ink = _glyph_from_box(rgb, (x0, y0, x1, y1))
            code, confidence = _classify(ink, templates)
            sequence.append(CellRead(code, confidence, (x0, y0, x1, y1)))
        sequences.append(sequence)
    return sequences


def _count_buffer(rgb):
    """数缓冲区里的空槽。数不清时返回 8 和 False。"""
    gray = rgb.astype(np.float32).mean(axis=2)  # 亮度
    height, width = gray.shape
    bright = gray > 55
    lines = []  # 较长的横线 (y, x0, x1)
    y_start = int(height * 0.05)
    y_stop = int(height * 0.42)
    min_run = int(width * 0.12)
    for y in range(y_start, y_stop):
        xs = np.flatnonzero(bright[y])
        if len(xs) == 0:
            continue
        start = int(xs[0])
        prev_x = int(xs[0])
        best = None
        for x in list(xs[1:]) + [10 ** 9]:
            x = int(x)
            if x > prev_x + 2:
                run = prev_x - start + 1
                if run >= min_run and (best is None or run > best[0]):
                    best = (run, start, prev_x)
                start = x
            prev_x = x
        if best is not None:
            lines.append((y, best[1], best[2]))
    pairs = []  # 可能是缓冲框上下边的一对横线
    for index, top in enumerate(lines):
        for bottom in lines[index + 1:index + 50]:
            gap = bottom[0] - top[0]
            if gap < height * 0.02 or gap > height * 0.12:
                continue
            overlap = min(top[2], bottom[2]) - max(top[1], bottom[1])
            span = max(top[2], bottom[2]) - min(top[1], bottom[1])
            if span <= 0 or overlap < span * 0.8:
                continue
            ratio = span / gap
            if ratio < 3 or ratio > 12:
                continue
            pairs.append((top[0], bottom[0], max(top[1], bottom[1]), min(top[2], bottom[2])))
    if not pairs:
        return 8, False
    ranked = []  # (自相关强度, 格数, 是否靠近画面中央)
    image_width = gray.shape[1]  # 截图宽度
    for top, bottom, x0, x1 in pairs:
        counted = _count_slots(gray, top, bottom, x0, x1)
        if counted is None:
            continue
        count, energy = counted
        center = (x0 + x1) / 2
        near_center = image_width * 0.30 <= center <= image_width * 0.75
        ranked.append((energy, count, near_center))
    if not ranked:
        return 8, False
    centered = [item for item in ranked if item[2]]  # 缓冲区在画面上方中间
    pool = centered or ranked
    pool.sort(reverse=True)
    _energy, count, _near = pool[0]
    return count, True


def _count_slots(gray, top, bottom, x0, x1):
    """在缓冲框内部，用虚线槽的重复间距算出格数。返回 (格数, 强度)。"""
    frame_width = x1 - x0  # 外框宽度
    frame_height = bottom - top  # 外框高度
    inset_x = max(4, int(frame_width * 0.04))  # 躲开实线外框
    inset_y = max(2, int(frame_height * 0.15))
    x0 += inset_x
    x1 -= inset_x
    y0 = top + inset_y
    y1 = bottom - inset_y
    if y1 <= y0 + 4 or x1 <= x0 + 20:
        return None
    region = gray[y0:y1, x0:x1]  # 虚线槽所在的内部区域
    span = region.shape[1]
    lag_min = max(8, span // 16)  # 格子间距的下限
    lag_max = max(lag_min + 1, span // 5)
    best_energy = 0  # 最强的周期信号
    best_lag = None  # 对应的格子间距
    best_row = None  # 虚线最清楚的那一行
    for row_index in range(region.shape[0]):
        row = region[row_index]
        if float(row.max()) < 40:
            continue
        centered = row - row.mean()
        corr = np.correlate(centered, centered, mode="full")
        corr = corr[len(corr) // 2:]
        upper = min(lag_max, len(corr) - 2)
        for lag in range(lag_min, upper):
            energy = float(corr[lag])
            if energy >= float(corr[lag - 1]) and energy >= float(corr[lag + 1]) and energy > best_energy:
                best_energy = energy
                best_lag = lag
                best_row = row_index
    if best_lag is None or best_energy < 1000:
        return None
    band_top = max(0, best_row - 1)
    band_bottom = min(region.shape[0], best_row + 2)
    band = region[band_top:band_bottom].max(axis=0)
    level = max(50.0, float(band.max()) * 0.55)  # 只留比较亮的虚线角点
    peaks = []  # 角点的横坐标
    for index in range(1, len(band) - 1):
        value = float(band[index])
        if value < level or value < float(band[index - 1]) or value < float(band[index + 1]):
            continue
        if peaks and index - peaks[-1] < best_lag * 0.25:
            if value > float(band[peaks[-1]]):
                peaks[-1] = index
        else:
            peaks.append(index)
    if len(peaks) < 4:
        return None
    width = peaks[-1] - peaks[0]  # 第一格到最后一格的跨度
    count = int(round(width / best_lag))
    if count < 2 or count > 12:
        return None
    if abs(width / best_lag - count) > 0.22:
        return None
    return count, best_energy


def is_uncertain(confidence):
    """置信度低于这个值时，界面上把格子标红。"""
    return confidence < 0.03
