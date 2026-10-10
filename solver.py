"""赛博朋克 2077 入侵协议路线求解。

路线规则来自 zlmturnout/Cyberpunk_CodeMatrix_decipher。
这里改成边走边剪枝，避免把 7×7、缓冲 8 的全部路线都存下来。
"""

# 游戏里会出现的全部代码
CODES = ("1C", "55", "7A", "BD", "E9", "FF")


def solve(matrix, sequences, buffer_size):
    """在代码矩阵里搜索最优上传路线。

    matrix 是方形矩阵，sequences 是要上传的代码序列，buffer_size 是缓冲区格数。
    优先完成更多序列，其次优先更长的序列，最后优先更短的路径。
    """
    size = len(matrix)  # 矩阵边长
    if size == 0 or any(len(row) != size for row in matrix):
        raise ValueError("代码矩阵必须是方形")
    if buffer_size < 1:
        raise ValueError("缓冲区长度至少为 1")

    code_ids = {code: index for index, code in enumerate(CODES)}  # 代码到编号
    grid = []  # 用编号表示的矩阵，加快比较
    for row in matrix:
        numbered = []
        for code in row:
            if code not in code_ids:
                raise ValueError("无法识别的代码：%s" % code)
            numbered.append(code_ids[code])
        grid.append(tuple(numbered))
    seqs = []  # 用编号表示的目标序列
    for sequence in sequences:
        if not sequence:
            continue
        numbered = []
        for code in sequence:
            if code not in code_ids:
                raise ValueError("无法识别的代码：%s" % code)
            numbered.append(code_ids[code])
        seqs.append(tuple(numbered))

    target_count = len(seqs)  # 序列总数
    target_sum = sum(len(sequence) for sequence in seqs)  # 全部序列的长度和
    best_score = (-1, -1, -(buffer_size + 1))  # (完成条数, 长度和, 负的步数)
    best_path = []  # 当前最优坐标

    path_rc = [None] * buffer_size  # 当前路径坐标
    path_code = [0] * buffer_size  # 当前路径代码编号

    def consider(length, done_mask):
        """用当前路径更新最优解。返回这一支是否还值得往下走。"""
        nonlocal best_score, best_path
        done_count = 0  # 已完成条数
        done_sum = 0  # 已完成序列的长度和
        for index, sequence in enumerate(seqs):
            if done_mask & (1 << index):
                done_count += 1
                done_sum += len(sequence)
        score = (done_count, done_sum, -length)
        if score > best_score:
            best_score = score
            best_path = path_rc[:length]
        if length == buffer_size:
            return False
        # 乐观估计：再走一步就能完成剩下的全部序列。到不了当前最优就剪枝
        optimistic = (
            target_count,
            target_sum,
            -(length if done_count == target_count else length + 1),
        )
        return optimistic > best_score

    def absorb(length, done_mask):
        """把以当前格子结尾的序列标记为完成。"""
        for index, sequence in enumerate(seqs):
            if done_mask & (1 << index):
                continue
            seq_len = len(sequence)
            if length < seq_len:
                continue
            start = length - seq_len
            same = True
            for offset in range(seq_len):
                if path_code[start + offset] != sequence[offset]:
                    same = False
                    break
            if same:
                done_mask |= 1 << index
        return done_mask

    def dfs(row, col, used, length, done_mask, next_is_row):
        """从当前格子继续走。next_is_row 为真时下一步沿行选。"""
        done_mask = absorb(length, done_mask)
        if not consider(length, done_mask):
            return
        if next_is_row:
            for next_col in range(size):
                bit = 1 << (row * size + next_col)
                if next_col == col or used & bit:
                    continue
                path_rc[length] = (row, next_col)
                path_code[length] = grid[row][next_col]
                dfs(row, next_col, used | bit, length + 1, done_mask, False)
        else:
            for next_row in range(size):
                bit = 1 << (next_row * size + col)
                if next_row == row or used & bit:
                    continue
                path_rc[length] = (next_row, col)
                path_code[length] = grid[next_row][col]
                dfs(next_row, col, used | bit, length + 1, done_mask, True)

    for start_col in range(size):
        path_rc[0] = (0, start_col)
        path_code[0] = grid[0][start_col]
        dfs(0, start_col, 1 << start_col, 1, 0, False)

    codes = [matrix[row][col] for row, col in best_path]  # 路线上的代码
    completed = []  # 完成的序列下标
    missed = []  # 没完成的序列下标
    for index, sequence in enumerate(sequences):
        if not sequence:
            missed.append(index)
            continue
        seq_len = len(sequence)
        found = any(
            codes[start:start + seq_len] == sequence
            for start in range(len(codes) - seq_len + 1)
        )
        if found:
            completed.append(index)
        else:
            missed.append(index)
    return {
        "path": best_path,
        "codes": codes,
        "completed": completed,
        "missed": missed,
    }
