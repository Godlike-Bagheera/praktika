"""Генерация уведомлений о упоминаниях (@username) в сообщениях."""

import re

from django.contrib.auth import get_user_model
from django.db.models.functions import Lower

from .models import Post, UserMention

# @имя: буквы (включая кириллицу), цифры, подчёркивание; длина как у username.
MENTION_RE = re.compile(r"@([\wА-Яа-яЁё]{1,150})")


def notify_mentions(post: Post) -> int:
    """Создаёт уведомления всем пользователям, упомянутым в тексте поста.

    Автор поста не уведомляется сам себя; дубликаты в одном посте схлопываются;
    уже уведомлённые по этому посту пользователи пропускаются.
    Возвращает количество созданных уведомлений.
    """
    usernames = {m.lower() for m in MENTION_RE.findall(post.text or "")}
    if not usernames:
        return 0

    User = get_user_model()
    targets = list(
        User.objects.annotate(uname_lower=Lower("username"))
        .filter(uname_lower__in=usernames)
        .exclude(pk=post.owner_id)
        .values_list("pk", "uname_lower")
    )
    # Самоупоминание не уведомляет, но остаётся в тексте.
    if not targets:
        return 0

    mentioned_ids = [pk for pk, _ in targets]
    already = set(
        UserMention.objects.filter(post=post, user_id__in=mentioned_ids)
        .values_list("user_id", flat=True)
    )
    to_create = [
        UserMention(user_id=pk, post=post)
        for pk, _name in targets if pk not in already
    ]
    if to_create:
        UserMention.objects.bulk_create(to_create)
    return len(to_create)
