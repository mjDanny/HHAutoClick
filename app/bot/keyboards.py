from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def vacancy_review_keyboard(vacancy_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Apply", callback_data=f"apply:{vacancy_id}"),
                InlineKeyboardButton(text="Rewrite", callback_data=f"rewrite:{vacancy_id}"),
            ],
            [
                InlineKeyboardButton(text="Skip", callback_data=f"skip:{vacancy_id}"),
                InlineKeyboardButton(text="Open on hh.ru", callback_data=f"open:{vacancy_id}"),
            ],
        ]
    )

