"""Ask Jev to pick a move from a position. Code generates the legal moves; Jev selects one."""
import os, pathlib, chess
from typesafe_sdk import TypeSafeClient, Choice

def load_env(path=".env"):
    p = pathlib.Path(path)
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

PIECE = {chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop",
         chess.ROOK: "rook", chess.QUEEN: "queen", chess.KING: "king"}

def describe(board: chess.Board, move: chess.Move) -> str:
    """Plain-English gloss of one move, so the model need not read geometry off the FEN."""
    pc = board.piece_at(move.from_square)
    frm, to = chess.square_name(move.from_square), chess.square_name(move.to_square)
    if board.is_kingside_castling(move):
        return "castles kingside"
    if board.is_queenside_castling(move):
        return "castles queenside"
    parts = [f"{PIECE[pc.piece_type]} {frm} to {to}"]
    victim = board.piece_at(move.to_square)
    if board.is_en_passant(move):
        parts.append("captures pawn en passant")
    elif victim:
        parts.append(f"captures {PIECE[victim.piece_type]}")
    if move.promotion:
        parts.append(f"promotes to {PIECE[move.promotion]}")
    board.push(move)
    if board.is_checkmate():
        parts.append("checkmate")
    elif board.is_check():
        parts.append("gives check")
    board.pop()
    return ", ".join(parts)

def state_for(board: chess.Board) -> dict:
    return {
        "board": str(board),
        "fen": board.fen(),
        "side_to_move": "white" if board.turn == chess.WHITE else "black",
        "fullmove_number": board.fullmove_number,
    }

def move_question(board: chess.Board, arm: str = "glossed") -> tuple[Choice, dict]:
    """arm: stripped (no +/# in labels) | bare (raw SAN) | glossed (SAN + description)."""
    criteria, by_san = {}, {}
    for mv in list(board.legal_moves):
        san = board.san(mv)
        key = san.rstrip("+#") if arm == "stripped" else san
        criteria[key] = describe(board, mv) if arm == "glossed" else None
        by_san[key] = mv
    side = "White" if board.turn == chess.WHITE else "Black"
    q = Choice(
        instructions=(
            f"It is {side}'s turn. Every option is a legal move for {side} in the position "
            f"given in `board` and `fen`. Select the move that is objectively strongest for "
            f"{side}: the move a strong player would choose, weighing material won or lost, "
            f"threats created, king safety, and piece activity. Judge the position after the "
            f"move, including what the opponent can play in reply."
        ),
        criteria=criteria,
    )
    return q, by_san
