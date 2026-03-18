from models.schemas import Phase

MAX_EXCHANGES = 20  # raw exchanges kept before compression trigger


class ShortTermMemory:
    """
    Manages the in-context conversation window.
    Stores raw exchanges as dicts: {role, content, phase}
    Triggers compression signal when window exceeds MAX_EXCHANGES.
    """

    def __init__(self):
        self._exchanges: list[dict] = []
        self._exchange_count: int = 0  # monotonic, never resets

    def add(self, role: str, content: str, phase: Phase) -> None:
        self._exchanges.append({
            "role": role,
            "content": content,
            "phase": phase
        })
        self._exchange_count += 1

    def get_window(self) -> list[dict]:
        """Returns current raw window for context builder."""
        return list(self._exchanges)

    def needs_compression(self) -> bool:
        return len(self._exchanges) >= MAX_EXCHANGES

    def flush_for_compression(self) -> tuple[list[dict], int, int]:
        """
        Returns exchanges to compress and their range.
        Keeps last 5 exchanges in window for continuity.
        """
        to_compress = self._exchanges[:-5]
        start = self._exchange_count - len(self._exchanges)
        end = start + len(to_compress)
        self._exchanges = self._exchanges[-5:]
        return to_compress, start, end

    def clear(self) -> None:
        self._exchanges = []

    @property
    def count(self) -> int:
        return self._exchange_count