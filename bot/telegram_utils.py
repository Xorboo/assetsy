import re


class TelegramUtils:
    @staticmethod
    def escape_markdown_v2(text: str) -> str:
        special_characters = r"_*[]()~`>#+-=|{}.!"
        return re.sub(f"([{re.escape(special_characters)}])", r"\\\1", text)

    @staticmethod
    def escape_markdown_v2_url(url: str) -> str:
        return re.sub(r"([()\\])", r"\\\1", url)

    @staticmethod
    def escape_markdown_v2_code(text: str) -> str:
        return re.sub(r"([`\\])", r"\\\1", text)
