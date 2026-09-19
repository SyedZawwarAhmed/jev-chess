# jev-chess

Play chess in the browser against [Jev](https://typesafe.sh), a System One model that
answers typed questions instead of generating text.

Jev never writes a move. `python-chess` enumerates every legal move in the position and
hands them over as the options of a single `Choice` question; Jev returns one option plus
a probability over all of them. An illegal move is not something the model can express.

The sidebar shows what that looks like from the inside: the top candidates with their
probabilities, the confidence in the move it took, how many options it was choosing
between, latency, and input tokens.

## Run it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # add your TYPESAFE_API_KEY
python server.py            # http://127.0.0.1:8111
```

The key is read once at startup and stays in the server process. The browser talks only
to localhost.

## Layout

```
server.py         stdlib HTTP server: /api/new, /api/move, /api/undo, and the page itself
jevchess/ask.py   builds the Choice question from a board, one option per legal move
web/index.html    the board, drag and drop, and the decision panel. No build step, no deps.
```

Games live in memory, keyed by an id the client holds. Restart the server and they are gone.

## Notes

Undo takes back two plies, so it is your turn again. Move labels are plain SAN, which does
leak a little: `Qxh5#` announces the mate before Jev has judged anything. `jevchess/ask.py`
also carries a `stripped` mode that removes the `+`/`#` suffixes, and a `glossed` mode that
adds a description of each move, if you want to see how much the notation is doing.
