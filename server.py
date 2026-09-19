"""Local server for playing Jev. The API key never leaves this process."""
import json, pathlib, time, uuid, traceback
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import chess
from jevchess.ask import load_env, move_question, state_for
from typesafe_sdk import TypeSafeClient

ROOT = pathlib.Path(__file__).parent
load_env(str(ROOT / ".env"))
client = TypeSafeClient(timeout=60.0)
GAMES: dict[str, chess.Board] = {}

def snapshot(board, extra=None):
    out = {
        "fen": board.fen(),
        "turn": "white" if board.turn == chess.WHITE else "black",
        "legal": [m.uci() for m in board.legal_moves],
        "last": board.peek().uci() if board.move_stack else None,
        "check": board.is_check(),
        "over": board.is_game_over(),
        "result": board.result() if board.is_game_over() else None,
        "reason": outcome_reason(board),
        "pgn": " ".join(moves_san(board)),
    }
    out.update(extra or {})
    return out

def outcome_reason(board):
    if not board.is_game_over():
        return None
    o = board.outcome()
    return o.termination.name.replace("_", " ").lower() if o else None

def moves_san(board):
    replay, sans = chess.Board(), []
    for mv in board.move_stack:
        sans.append(replay.san(mv)); replay.push(mv)
    return sans

def jev_move(board, arm):
    """Code generates every legal move; Jev only selects one."""
    q, by_key = move_question(board, arm)
    t0 = time.time()
    r = client.system_one(state_for(board), {"move": q})
    a = r.answers["move"]
    top = sorted(a.probabilities.items(), key=lambda kv: -kv[1])[:6]
    mv = by_key.get(a.choice) or next(iter(by_key.values()))   # never trust a label blindly
    san = board.san(mv)
    board.push(mv)
    return {
        "jev": {
            "san": san, "uci": mv.uci(), "confidence": round(a.confidence, 3),
            "candidates": [{"move": k, "p": round(p, 4)} for k, p in top],
            "latency": round(time.time() - t0, 2),
            "tokens": r.usage.input_tokens, "model": r.model,
            "n_options": len(by_key), "arm": arm,
        }
    }

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _send(self, code, body, ctype="application/json"):
        raw = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path.startswith("/favicon.ico"):
            return self._send(204, b"", "image/x-icon")
        if self.path.split("?")[0] in ("/", "/index.html"):
            self._send(200, (ROOT / "web/index.html").read_bytes(), "text/html; charset=utf-8")
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
            req = json.loads(self.rfile.read(n) or b"{}")
            path = self.path.split("?")[0]

            if path == "/api/new":
                gid = uuid.uuid4().hex[:12]
                board = chess.Board()
                GAMES[gid] = board
                extra = {"id": gid}
                # Jev is White: it opens.
                if req.get("human_color") == "black" and not board.is_game_over():
                    extra.update(jev_move(board, req.get("arm", "bare")))
                return self._send(200, snapshot(board, extra))

            if path == "/api/move":
                board = GAMES.get(req.get("id"))
                if board is None:
                    return self._send(404, {"error": "no such game"})
                mv = chess.Move.from_uci(req["uci"])
                if mv not in board.legal_moves:
                    return self._send(400, {"error": f"illegal move {req['uci']}"})
                board.push(mv)
                extra = {"id": req["id"]}
                if not board.is_game_over():
                    extra.update(jev_move(board, req.get("arm", "bare")))
                return self._send(200, snapshot(board, extra))

            if path == "/api/undo":
                board = GAMES.get(req.get("id"))
                if board is None:
                    return self._send(404, {"error": "no such game"})
                for _ in range(min(2, len(board.move_stack))):
                    board.pop()
                return self._send(200, snapshot(board, {"id": req["id"]}))

            self._send(404, {"error": "not found"})
        except Exception as e:
            traceback.print_exc()
            self._send(500, {"error": f"{type(e).__name__}: {e}"})

if __name__ == "__main__":
    print("jev-chess  ->  http://127.0.0.1:8111")
    ThreadingHTTPServer(("127.0.0.1", 8111), Handler).serve_forever()
